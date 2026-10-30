from datetime import datetime, timedelta, timezone
from backend.app.models import Agent, Borrower, Call
from backend.app.models.enums import AgentState, BorrowerStatus, CallState, ProviderType
from backend.app.services.recovery_service import RecoveryService

def test_stale_reservation_reaper_worker_crash(db_session):
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=25)  # 25 seconds ago (TTL is 10s)

    # Agent left in RESERVED by crashed worker
    agent = Agent(id=1, name="CrashedAgent", status=AgentState.RESERVED.value, reserved_at=stale_time, version=1)
    # Borrower left in RESERVED by crashed worker
    borrower = Borrower(id=1, name="CrashedBorrower", phone="+919999999999", status=BorrowerStatus.RESERVED.value, reserved_at=stale_time, version=1)

    db_session.add_all([agent, borrower])
    db_session.commit()

    stats = RecoveryService.reap_stale_reservations(db_session, ttl_seconds=10)
    assert stats["reaped_agents"] == 1
    assert stats["reaped_borrowers"] == 1

    db_session.refresh(agent)
    db_session.refresh(borrower)

    # Both restored to available pools
    assert agent.status == AgentState.AVAILABLE.value
    assert agent.reserved_at is None
    assert agent.version == 2

    assert borrower.status == BorrowerStatus.QUEUED.value
    assert borrower.reserved_at is None
    assert borrower.version == 2

def test_orphaned_call_reaper_worker_crash(db_session):
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=60)  # 60s ago (Timeout is 45s)

    agent = Agent(id=2, name="Agent-Call-Crash", status=AgentState.DIALING.value, version=1)
    borrower = Borrower(id=2, name="Borrower-Call-Crash", phone="+919999999998", status=BorrowerStatus.DIALING.value, version=1)
    db_session.add_all([agent, borrower])
    db_session.commit()

    call = Call(
        id=99,
        idempotency_key="crash-call-99",
        campaign_id=1,
        borrower_id=2,
        agent_id=2,
        provider_type=ProviderType.PROVIDER_A.value,
        status=CallState.INITIATED.value,
        created_at=old_time
    )
    db_session.add(call)
    db_session.commit()

    stats = RecoveryService.reap_orphaned_calls(db_session, timeout_seconds=45)
    assert stats["timed_out_orphaned_calls"] == 1

    db_session.refresh(call)
    db_session.refresh(agent)
    db_session.refresh(borrower)

    assert call.status == CallState.FAILED.value
    assert "ORPHANED_TIMEOUT_REAPER" in call.failure_reason
    # Associated agent and borrower freed
    assert agent.status == AgentState.AVAILABLE.value
    assert borrower.status == BorrowerStatus.QUEUED.value
