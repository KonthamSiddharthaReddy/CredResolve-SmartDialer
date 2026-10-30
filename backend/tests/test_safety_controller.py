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
