from datetime import datetime, timedelta, timezone
from backend.app.models import Agent, Borrower, Call
from backend.app.models.enums import AgentState, BorrowerStatus, CallState, ProviderType
from backend.app.services.recovery_service import RecoveryService
from backend.app.services.dialer_worker import DialerWorker

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

def test_stale_call_reservation_reaper_worker_crash(db_session):
    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=25)

    call = Call(
        id=77,
        idempotency_key="stale-reserved-call-77",
        campaign_id=1,
        borrower_id=1,
        provider_type=ProviderType.PROVIDER_A.value,
        status=CallState.RESERVED.value,
        reserved_at=stale_time
    )
    db_session.add(call)
    db_session.commit()

    stats = RecoveryService.reap_stale_reservations(db_session, ttl_seconds=10)
    assert stats["reaped_calls"] == 1

    db_session.refresh(call)
    assert call.status == CallState.FAILED.value
    assert "WORKER_CRASH_BEFORE_DISPATCH" in call.failure_reason

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

def test_orphaned_answered_call_reaper_worker_crash(db_session):
    now = datetime.now(timezone.utc)
    old_time = now - timedelta(seconds=60)

    call = Call(
        id=101,
        idempotency_key="crash-answered-101",
        campaign_id=1,
        borrower_id=1,
        provider_type=ProviderType.PROVIDER_A.value,
        status=CallState.ANSWERED.value,
        created_at=old_time
    )
    db_session.add(call)
    db_session.commit()

    stats = RecoveryService.reap_orphaned_calls(db_session, timeout_seconds=45)
    assert stats["timed_out_orphaned_calls"] == 1

    db_session.refresh(call)
    assert call.status == CallState.FAILED.value
    assert "ORPHANED_TIMEOUT_REAPER" in call.failure_reason

def test_agent_disappears_during_call_setup_dynamic_rescue(db_session):
    # Agent 10 was assigned but goes OFFLINE during ringing
    agent_disappeared = Agent(id=10, name="DisappearingAgent", status=AgentState.OFFLINE.value)
    # Agent 11 is available in the pool
    agent_rescue = Agent(id=11, name="RescueAgent", status=AgentState.AVAILABLE.value)
    borrower = Borrower(id=10, name="Borrower-10", phone="+919876543210", status=BorrowerStatus.DIALING.value)
    
    db_session.add_all([agent_disappeared, agent_rescue, borrower])
    db_session.commit()

    call = Call(
        id=202,
        idempotency_key="disappear-202",
        campaign_id=1,
        borrower_id=10,
        agent_id=10,  # Points to disappeared agent
        provider_type=ProviderType.PROVIDER_A.value,
        status=CallState.RINGING.value
    )
    db_session.add(call)
    db_session.commit()

    # Call answers!
    res = DialerWorker.process_call_answered(db_session, call.id)
    assert res["status"] == "connected"
    assert res["agent_id"] == 11  # Dynamically rescued and bridged to Agent 11!
    
    db_session.refresh(call)
    db_session.refresh(agent_rescue)
    assert call.agent_id == 11
    assert call.status == CallState.CONNECTED.value
    assert agent_rescue.status == AgentState.CONNECTED.value
    assert call.is_abandoned is False

def test_agent_disappears_during_call_setup_agent_exhaustion(db_session):
    # Agent 20 goes OFFLINE during ringing, and NO other agent is available
    agent_disappeared = Agent(id=20, name="DisappearingAgent-20", status=AgentState.OFFLINE.value)
    borrower = Borrower(id=20, name="Borrower-20", phone="+919876543220", status=BorrowerStatus.DIALING.value)
    db_session.add_all([agent_disappeared, borrower])
    db_session.commit()

    call = Call(
        id=303,
        idempotency_key="disappear-exhaust-303",
        campaign_id=1,
        borrower_id=20,
        agent_id=20,
        provider_type=ProviderType.PROVIDER_A.value,
        status=CallState.RINGING.value
    )
    db_session.add(call)
    db_session.commit()

    res = DialerWorker.process_call_answered(db_session, call.id)
    assert res["status"] == "abandoned"

    db_session.refresh(call)
    assert call.is_abandoned is True
    assert call.status == CallState.FAILED.value
    assert "ABANDONED_CALL" in call.failure_reason
