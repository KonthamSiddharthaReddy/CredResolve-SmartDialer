from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from sqlalchemy import select, update
from sqlalchemy.orm import Session
from backend.app.models import Agent, Borrower, Call
from backend.app.models.enums import AgentState, BorrowerStatus, CallState
from backend.app.config import settings

class RecoveryService:
    """
    Janitor / Crash Recovery Service:
    - Scans for stale reservations caused by worker crashes.
    - Recovers orphaned agents and borrowers back to active pools.
    - Times out orphaned calls stuck in INITIATED or RINGING without provider callbacks.
    """

    @staticmethod
    def reap_stale_reservations(db: Session, ttl_seconds: int = None) -> Dict[str, int]:
        ttl = ttl_seconds if ttl_seconds is not None else settings.RESERVATION_TTL_SECONDS
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=ttl)

        # 1. Reap Stale Agent Reservations
        stale_agents = (
            db.execute(
                select(Agent)
                .where(
                    Agent.status == AgentState.RESERVED.value,
                    Agent.reserved_at <= cutoff
                )
            )
            .scalars()
            .all()
        )

        reaped_agents_count = 0
        now = datetime.now(timezone.utc)
        for agent in stale_agents:
            agent.status = AgentState.AVAILABLE.value
            agent.reserved_at = None
            agent.current_call_id = None
            agent.last_status_change = now
            agent.version += 1
            reaped_agents_count += 1

        # 2. Reap Stale Borrower Reservations
        stale_borrowers = (
            db.execute(
                select(Borrower)
                .where(
                    Borrower.status == BorrowerStatus.RESERVED.value,
                    Borrower.reserved_at <= cutoff
                )
            )
            .scalars()
            .all()
        )

        reaped_borrowers_count = 0
        for borrower in stale_borrowers:
            borrower.status = BorrowerStatus.QUEUED.value
            borrower.reserved_at = None
            borrower.version += 1
            reaped_borrowers_count += 1

        if reaped_agents_count > 0 or reaped_borrowers_count > 0:
            db.commit()

        return {
            "reaped_agents": reaped_agents_count,
            "reaped_borrowers": reaped_borrowers_count
        }

    @staticmethod
    def reap_orphaned_calls(db: Session, timeout_seconds: int = None) -> Dict[str, int]:
        timeout = timeout_seconds if timeout_seconds is not None else settings.CALL_INITIATION_TIMEOUT_SECONDS
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=timeout)

        # Calls stuck in INITIATED or RINGING past timeout threshold
        orphaned_calls = (
            db.execute(
                select(Call)
                .where(
                    Call.status.in_([CallState.INITIATED.value, CallState.RINGING.value, CallState.ANSWERED.value]),
                    Call.created_at <= cutoff
                )
            )
            .scalars()
            .all()
        )

        timed_out_count = 0
        now = datetime.now(timezone.utc)
        for call in orphaned_calls:
            call.status = CallState.FAILED.value
            call.failure_reason = "ORPHANED_TIMEOUT_REAPER: Worker crash or missing carrier webhook"
            call.completed_at = now
            call.version += 1
            timed_out_count += 1

            # Release associated agent if still held
            if call.agent_id:
                agent = db.execute(select(Agent).where(Agent.id == call.agent_id)).scalar_one_or_none()
                if agent and agent.status in {AgentState.DIALING.value, AgentState.RESERVED.value}:
                    agent.status = AgentState.AVAILABLE.value
                    agent.current_call_id = None
                    agent.reserved_at = None
                    agent.last_status_change = now
                    agent.version += 1

            # Release associated borrower if still in dialing state
            if call.borrower_id:
                borrower = db.execute(select(Borrower).where(Borrower.id == call.borrower_id)).scalar_one_or_none()
                if borrower and borrower.status == BorrowerStatus.DIALING.value:
                    borrower.status = BorrowerStatus.QUEUED.value
                    borrower.reserved_at = None
                    borrower.version += 1

        if timed_out_count > 0:
            db.commit()

        return {"timed_out_orphaned_calls": timed_out_count}
