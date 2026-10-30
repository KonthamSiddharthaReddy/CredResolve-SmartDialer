import pytest
from backend.app.models import Agent, Call
from backend.app.models.enums import AgentState, CallState, ProviderType
from backend.app.state_machines.agent_state_machine import AgentStateMachine, InvalidAgentStateTransitionException
from backend.app.state_machines.call_state_machine import CallStateMachine, InvalidCallStateTransitionException

def test_agent_valid_lifecycle():
    agent = Agent(id=1, name="Agent-01", status=AgentState.OFFLINE.value)
    
    AgentStateMachine.transition(agent, AgentState.AVAILABLE)
    assert agent.status == AgentState.AVAILABLE.value
    
    AgentStateMachine.transition(agent, AgentState.RESERVED)
    assert agent.status == AgentState.RESERVED.value
    assert agent.reserved_at is not None
    
    AgentStateMachine.transition(agent, AgentState.DIALING)
    assert agent.status == AgentState.DIALING.value
    
    AgentStateMachine.transition(agent, AgentState.CONNECTED)
    assert agent.status == AgentState.CONNECTED.value
    assert agent.connected_at is not None
    
    AgentStateMachine.transition(agent, AgentState.WRAP_UP)
    assert agent.status == AgentState.WRAP_UP.value
    
    AgentStateMachine.transition(agent, AgentState.AVAILABLE)
    assert agent.status == AgentState.AVAILABLE.value
    assert agent.reserved_at is None
    assert agent.connected_at is None

def test_agent_invalid_transitions():
    agent = Agent(id=2, name="Agent-02", status=AgentState.OFFLINE.value)
    
    # OFFLINE cannot jump directly to CONNECTED
    with pytest.raises(InvalidAgentStateTransitionException):
        AgentStateMachine.transition(agent, AgentState.CONNECTED)
        
    # WRAP_UP cannot jump directly to DIALING
    agent.status = AgentState.WRAP_UP.value
    with pytest.raises(InvalidAgentStateTransitionException):
        AgentStateMachine.transition(agent, AgentState.DIALING)

def test_call_valid_lifecycle():
    call = Call(id=1, idempotency_key="k1", campaign_id=1, borrower_id=1, provider_type=ProviderType.PROVIDER_A.value, status=CallState.QUEUED.value)
    
    CallStateMachine.transition(call, CallState.RESERVED)
    assert call.status == CallState.RESERVED.value
    
    CallStateMachine.transition(call, CallState.INITIATED)
    assert call.status == CallState.INITIATED.value
    assert call.initiated_at is not None
    
    CallStateMachine.transition(call, CallState.RINGING)
    assert call.status == CallState.RINGING.value
    assert call.ringing_at is not None
    
    CallStateMachine.transition(call, CallState.ANSWERED)
    assert call.status == CallState.ANSWERED.value
    assert call.answered_at is not None
    
    CallStateMachine.transition(call, CallState.CONNECTED)
    assert call.status == CallState.CONNECTED.value
    assert call.connected_at is not None
    
    CallStateMachine.transition(call, CallState.COMPLETED)
    assert call.status == CallState.COMPLETED.value
    assert call.completed_at is not None

def test_call_duplicate_events_idempotency():
    call = Call(id=2, idempotency_key="k2", campaign_id=1, borrower_id=1, provider_type=ProviderType.PROVIDER_A.value, status=CallState.ANSWERED.value)
    
    # Second duplicate ANSWERED event arrives
    res = CallStateMachine.transition(call, CallState.ANSWERED)
    assert res.success is True
    assert res.is_duplicate is True
    assert call.status == CallState.ANSWERED.value

def test_call_out_of_order_and_stale_events():
    # Scenario: COMPLETED arrives while in RINGING
    call = Call(id=3, idempotency_key="k3", campaign_id=1, borrower_id=1, provider_type=ProviderType.PROVIDER_B.value, status=CallState.RINGING.value)
    
    res = CallStateMachine.transition(call, CallState.COMPLETED)
    assert res.success is True
    assert res.is_out_of_order is True
    assert call.status == CallState.COMPLETED.value
    
    # Now delayed ANSWERED arrives for already COMPLETED call
    stale_res = CallStateMachine.transition(call, CallState.ANSWERED)
    assert stale_res.success is False
    assert stale_res.is_stale is True
    assert call.status == CallState.COMPLETED.value  # State remains COMPLETED!

def test_call_invalid_transition_from_terminal():
    call = Call(id=4, idempotency_key="k4", campaign_id=1, borrower_id=1, provider_type=ProviderType.PROVIDER_A.value, status=CallState.FAILED.value)
    
    # FAILED cannot transition to CONNECTED
    with pytest.raises(InvalidCallStateTransitionException):
        CallStateMachine.transition(call, CallState.CONNECTED)
