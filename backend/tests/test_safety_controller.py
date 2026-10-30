from backend.app.models.enums import DialingMode, SafetyDecisionType, CircuitState
from backend.app.pacing.base import PacingDecision
from backend.app.pacing.safety_controller import SafetyController

def test_safety_approves_safe_progressive():
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PROGRESSIVE, requested_calls=5)
    
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=5,
        ringing_calls=0,
        connected_calls=0,
        wrap_up_agents=0,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.01,
        recent_abandon_rate=0.0,
        recent_abandon_count=0,
        current_answer_rate=0.40
    )
    assert eval_res.decision_type == SafetyDecisionType.APPROVED
    assert eval_res.approved_calls == 5

def test_safety_clamps_progressive_over_request():
    controller = SafetyController()
    # Pacing engine buggy or rogue, requesting 15 calls with only 6 agents available
    pacing = PacingDecision(mode=DialingMode.PROGRESSIVE, requested_calls=15)
    
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=6,
        ringing_calls=1,
        connected_calls=0,
        wrap_up_agents=0,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.01,
        recent_abandon_rate=0.0,
        recent_abandon_count=0,
        current_answer_rate=0.40
    )
    # Must clamp to 6 - 1 = 5
    assert eval_res.decision_type == SafetyDecisionType.REDUCED
    assert eval_res.approved_calls == 5

def test_safety_fallback_on_recent_abandoned_call():
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PREDICTIVE, requested_calls=25)
    
    # 1 abandoned call recorded in recent history
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=8,
        ringing_calls=2,
        connected_calls=15,
        wrap_up_agents=1,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.01,
        recent_abandon_rate=0.02,
        recent_abandon_count=1,
        current_answer_rate=0.40
    )
    # Must force fallback to progressive mode
    assert eval_res.decision_type == SafetyDecisionType.FALLBACK_PROGRESSIVE
    assert eval_res.is_fallback is True
    # In progressive fallback, approved is clamped to available agents (8 - 2 = 6)
    assert eval_res.approved_calls == 6
    assert "Abandoned call threshold exceeded" in eval_res.rationale

def test_safety_fallback_on_circuit_breaker_open():
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PREDICTIVE, requested_calls=20)
    
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=10,
        ringing_calls=0,
        connected_calls=5,
        wrap_up_agents=0,
        circuit_state=CircuitState.OPEN,
        provider_failure_rate=0.50,
        recent_abandon_rate=0.0,
        recent_abandon_count=0,
        current_answer_rate=0.40
    )
    # When circuit is open, must reject speculative predictive calls
    assert eval_res.decision_type in {SafetyDecisionType.REJECTED, SafetyDecisionType.FALLBACK_PROGRESSIVE}
    assert eval_res.approved_calls == 0
    assert "Provider circuit is OPEN" in eval_res.rationale

def test_safety_fallback_on_answer_rate_crash():
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PREDICTIVE, requested_calls=30)
    
    # Answer rate collapsed to 5%
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=10,
        ringing_calls=0,
        connected_calls=10,
        wrap_up_agents=0,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.02,
        recent_abandon_rate=0.0,
        recent_abandon_count=0,
        current_answer_rate=0.05
    )
    assert eval_res.decision_type == SafetyDecisionType.FALLBACK_PROGRESSIVE
    assert eval_res.is_fallback is True
    assert eval_res.approved_calls <= 10

def test_safety_rejects_when_ringing_exceeds_available():
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PREDICTIVE, requested_calls=10)
    
    # E.g. Agents dropped suddenly from 20 to 5, but 8 calls are already in-flight ringing!
    eval_res = controller.evaluate(
        pacing_decision=pacing,
        available_agents=5,
        ringing_calls=8,
        connected_calls=2,
        wrap_up_agents=0,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.01,
        recent_abandon_rate=0.0,
        recent_abandon_count=0,
        current_answer_rate=0.40
    )
    assert eval_res.decision_type == SafetyDecisionType.REJECTED
    assert eval_res.approved_calls == 0


def test_safety_binomial_ucl_clamping():
    """
    Test that the Binomial Upper Confidence Limit (UCL) bound calculates
    a mathematically sound ceiling that clamps speculative overdialing.
    """
    controller = SafetyController(max_abandon_rate=0.01)
    
    # High answer rate (70%): an arbitrary 3.0x multiplier would dangerously dial 30 calls!
    # The Binomial UCL bound should strictly clamp it to a safe number (~10 calls).
    ceiling_high_ans = SafetyController.calculate_binomial_safe_dialing_ceiling(
        available_agents=10,
        wrap_up_agents=0,
        connected_calls=0,
        answer_rate=0.70,
        target_abandon_rate=0.01
    )
    assert ceiling_high_ans <= 12
    assert ceiling_high_ans >= 10

    # Low answer rate (20%): safe dialing ceiling expands naturally to ~26 calls.
    ceiling_low_ans = SafetyController.calculate_binomial_safe_dialing_ceiling(
        available_agents=10,
        wrap_up_agents=0,
        connected_calls=0,
        answer_rate=0.20,
        target_abandon_rate=0.01
    )
    assert ceiling_low_ans >= 20

def test_simultaneous_borrower_answers_insufficient_capacity(db_session):
    """
    PRIORITY 1.3 & 1.4: Test simultaneous borrower answers when available agent capacity is insufficient.
    Verify that no connected borrower is left in an unhandled/hanging state:
    Exactly available agents are bridged, and excess answered calls are explicitly marked ABANDONED.
    """
    from backend.app.models import Agent, Borrower, Call
    from backend.app.models.enums import AgentState, BorrowerStatus, CallState, ProviderType
    from backend.app.services.dialer_worker import DialerWorker

    # Exactly 2 available agents in the pool
    a1 = Agent(id=501, name="Agent-501", status=AgentState.AVAILABLE.value)
    a2 = Agent(id=502, name="Agent-502", status=AgentState.AVAILABLE.value)
    db_session.add_all([a1, a2])

    # 4 borrowers with in-flight ringing calls
    calls = []
    for i in range(1, 5):
        b = Borrower(id=600 + i, name=f"Borrower-{i}", phone=f"+91987654320{i}", status=BorrowerStatus.DIALING.value)
        db_session.add(b)
        c = Call(
            id=700 + i,
            idempotency_key=f"simul-ans-{i}",
            campaign_id=1,
            borrower_id=600 + i,
            agent_id=None,  # Speculative predictive call
            provider_type=ProviderType.PROVIDER_A.value,
            status=CallState.RINGING.value
        )
        db_session.add(c)
        calls.append(c)
    db_session.commit()

    # All 4 calls answer simultaneously!
    results = [DialerWorker.process_call_answered(db_session, c.id) for c in calls]

    # Verify: Exactly 2 connected, exactly 2 abandoned
    connected_res = [r for r in results if r["status"] == "connected"]
    abandoned_res = [r for r in results if r["status"] == "abandoned"]

    assert len(connected_res) == 2
    assert len(abandoned_res) == 2

    # Verify DB records
    db_session.refresh(calls[0])
    db_session.refresh(calls[1])
    db_session.refresh(calls[2])
    db_session.refresh(calls[3])

    connected_calls = [c for c in calls if c.status == CallState.CONNECTED.value]
    abandoned_calls = [c for c in calls if c.is_abandoned is True and c.status == CallState.FAILED.value]

    assert len(connected_calls) == 2
    assert len(abandoned_calls) == 2
    for ac in abandoned_calls:
        assert "ABANDONED_CALL" in ac.failure_reason

    # Verify Safety Controller responds by forcing progressive fallback on next cycle!
    controller = SafetyController()
    pacing = PacingDecision(mode=DialingMode.PREDICTIVE, requested_calls=10)
    safety_eval = controller.evaluate(
        pacing_decision=pacing,
        available_agents=2,
        ringing_calls=0,
        connected_calls=2,
        wrap_up_agents=0,
        circuit_state=CircuitState.CLOSED,
        provider_failure_rate=0.01,
        recent_abandon_rate=0.50,
        recent_abandon_count=2,
        current_answer_rate=0.50
    )
    assert safety_eval.decision_type == SafetyDecisionType.FALLBACK_PROGRESSIVE
    assert safety_eval.is_fallback is True
