from datetime import datetime, timezone
from typing import Optional, List, Tuple
from sqlalchemy import select, update, and_
from sqlalchemy.orm import Session
from backend.app.models import Agent, Borrower, Call
from backend.app.models.enums import AgentState, BorrowerStatus, CallState
from backend.app.state_machines.agent_state_machine import AgentStateMachine

class AllocationService:
    """
    Atomic Agent and Borrower Allocation Service.
    Guarantees concurrency safety using database conditional updates and versioning.
    Prevents race conditions between multiple concurrent dialer workers.
    """

    @staticmethod
    def reserve_agent_atomically(db: Session, agent_id: int, current_version: int) -> bool:
        """
        Atomically reserve an agent using optimistic concurrency.
        Returns True if reservation was successful, False if another worker got it first.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(Agent)
            .where(
                Agent.id == agent_id,
                Agent.status == AgentState.AVAILABLE.value,
                Agent.version == current_version
            )
            .values(
                status=AgentState.RESERVED.value,
                reserved_at=now,
                last_status_change=now,
                version=Agent.version + 1
            )
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    @staticmethod
    def reserve_next_available_agent(db: Session) -> Optional[Agent]:
        """
        Finds candidate available agents and attempts atomic reservation.
        Tolerates high concurrency: if worker A and B both see Agent #1,
        only one succeeds; the other automatically falls through to Agent #2.
        """
        candidates = (
            db.execute(
                select(Agent)
                .where(Agent.status == AgentState.AVAILABLE.value)
                .order_by(Agent.last_status_change.asc())
                .limit(10)
            )
            .scalars()
            .all()
        )

        for agent in candidates:
            success = AllocationService.reserve_agent_atomically(db, agent.id, agent.version)
            if success:
                db.refresh(agent)
                return agent
        return None

    @staticmethod
    def reserve_borrower_atomically(db: Session, borrower_id: int, current_version: int) -> bool:
        """
        Atomically reserve a borrower from the queue.
        Guarantees that a borrower is never called twice simultaneously.
        """
        now = datetime.now(timezone.utc)
        stmt = (
            update(Borrower)
            .where(
                Borrower.id == borrower_id,
                Borrower.status == BorrowerStatus.QUEUED.value,
                Borrower.version == current_version
            )
            .values(
                status=BorrowerStatus.RESERVED.value,
                reserved_at=now,
                dial_attempts=Borrower.dial_attempts + 1,
                last_attempt_at=now,
                version=Borrower.version + 1
            )
        )
        result = db.execute(stmt)
        db.commit()
        return result.rowcount > 0

    @staticmethod
    def reserve_next_queued_borrower(db: Session, campaign_id: int) -> Optional[Borrower]:
        """
        Finds prioritized candidate queued borrowers and attempts atomic reservation.
        """
        query = (
            select(Borrower)
            .where(
                Borrower.status == BorrowerStatus.QUEUED.value,
                (Borrower.campaign_id == campaign_id) | (Borrower.campaign_id.is_(None))
            )
            .order_by(Borrower.priority.desc(), Borrower.dial_attempts.asc(), Borrower.id.asc())
            .limit(10)
        )
        candidates = db.execute(query).scalars().all()

        for borrower in candidates:
            success = AllocationService.reserve_borrower_atomically(db, borrower.id, borrower.version)
            if success:
                db.refresh(borrower)
                return borrower
        return None

    @staticmethod
    def release_agent_to_available(db: Session, agent_id: int) -> bool:
        """
        Releases an agent back to AVAILABLE state.
        """
        agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
        if agent:
            now = datetime.now(timezone.utc)
            agent.status = AgentState.AVAILABLE.value
            agent.reserved_at = None
            agent.connected_at = None
            agent.current_call_id = None
            agent.last_status_change = now
            agent.version += 1
            db.commit()
            return True
        return False

    @staticmethod
    def release_borrower_to_queued(db: Session, borrower_id: int) -> bool:
        """
        Releases a borrower back to QUEUED state upon failed dial or aborted reservation.
        """
        borrower = db.execute(select(Borrower).where(Borrower.id == borrower_id)).scalar_one_or_none()
        if borrower:
            borrower.status = BorrowerStatus.QUEUED.value
            borrower.reserved_at = None
            borrower.version += 1
            db.commit()
            return True
        return False
