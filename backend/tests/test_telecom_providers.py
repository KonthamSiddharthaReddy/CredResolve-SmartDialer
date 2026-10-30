import pytest
from backend.app.telecom.provider_a import ProviderA
from backend.app.telecom.provider_b import ProviderB
from backend.app.models import Call, Agent, Borrower
from backend.app.models.enums import CallState, AgentState, BorrowerStatus, ProviderType
from backend.app.services.dialer_worker import DialerWorker

@pytest.mark.asyncio
async def test_provider_a_fast_reliable():
    pa = ProviderA()
    pa.failure_rate = 0.0  # Deterministic test
    res = await pa.initiate_call(call_id=1, phone="+919876543210", idempotency_key="k1")
    assert res.success is True
    assert res.provider_call_id.startswith("PA-1-")
    assert res.latency_ms < 300.0

@pytest.mark.asyncio
async def test_provider_b_timeout_behavior():
    pb = ProviderB()
    pb.force_timeouts = True  # Inject timeout
    res = await pb.initiate_call(call_id=2, phone="+919876543210", idempotency_key="k2")
    assert res.success is False
    assert res.is_timeout is True
    assert "Timeout" in res.error_message
    pb.force_timeouts = False

def test_duplicate_answered_events_handling(db_session):
    agent = Agent(id=1, name="Agent-01", status=AgentState.AVAILABLE.value)
    borrower = Borrower(id=1, name="Borrower-01", phone="+919999999999", status=BorrowerStatus.QUEUED.value)
    db_session.add_all([agent, borrower])
    db_session.commit()

    call = Call(
        id=10,
        idempotency_key="dup-key-10",
        campaign_id=1,
        borrower_id=1,
        agent_id=1,
        provider_type=ProviderType.PROVIDER_B.value,
        status=CallState.RINGING.value
    )
    db_session.add(call)
    db_session.commit()

    # 1st ANSWERED event
    res1 = DialerWorker.process_call_answered(db_session, call.id)
    assert res1["status"] == "connected"
    assert call.status == CallState.CONNECTED.value
    assert agent.status == AgentState.CONNECTED.value

    # 2nd ANSWERED event (duplicate from Provider B)
    res2 = DialerWorker.process_call_answered(db_session, call.id)
    assert res2["status"] == "duplicate"
    # Verify state was not corrupted or double-allocated
    assert call.status == CallState.CONNECTED.value
    assert agent.status == AgentState.CONNECTED.value

def test_out_of_order_completed_before_answered(db_session):
    agent = Agent(id=2, name="Agent-02", status=AgentState.DIALING.value)
    borrower = Borrower(id=2, name="Borrower-02", phone="+919999999998", status=BorrowerStatus.QUEUED.value)
    db_session.add_all([agent, borrower])
    db_session.commit()

    call = Call(
        id=20,
        idempotency_key="ooo-key-20",
        campaign_id=1,
        borrower_id=2,
        agent_id=2,
        provider_type=ProviderType.PROVIDER_B.value,
        status=CallState.RINGING.value
    )
    db_session.add(call)
    db_session.commit()

    # COMPLETED arrives first
    comp_res = DialerWorker.process_call_completed(db_session, call.id, talk_duration=15.0)
    assert comp_res["status"] == "completed"
    assert call.status == CallState.COMPLETED.value
    assert call.talk_duration_seconds == 15.0
    assert agent.status == AgentState.WRAP_UP.value

    # Delayed ANSWERED event arrives later
    late_ans_res = DialerWorker.process_call_answered(db_session, call.id)
    assert late_ans_res["status"] == "stale"
    assert call.status == CallState.COMPLETED.value
    assert agent.status == AgentState.WRAP_UP.value  # Agent is not reverted!
