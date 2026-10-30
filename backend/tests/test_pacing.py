from backend.app.models.enums import DialingMode
from backend.app.pacing.progressive import ProgressivePacingEngine
from backend.app.pacing.predictive import PredictivePacingEngine

def test_progressive_pacing_never_exceeds_available():
    engine = ProgressivePacingEngine()
    
    # 10 available, 0 ringing -> exactly 10
    d1 = engine.calculate_pacing(
        available_agents=10, connected_calls=0, ringing_calls=0, wrap_up_agents=0,
        historical_answer_rate=0.4, avg_talk_time_sec=90, avg_ring_time_sec=20,
        provider_latency_sec=0.1, provider_failure_rate=0.0
    )
    assert d1.mode == DialingMode.PROGRESSIVE
    assert d1.requested_calls == 10
    
    # 10 available, 4 already ringing -> 6 new calls
    d2 = engine.calculate_pacing(
        available_agents=10, connected_calls=0, ringing_calls=4, wrap_up_agents=0,
        historical_answer_rate=0.4, avg_talk_time_sec=90, avg_ring_time_sec=20,
        provider_latency_sec=0.1, provider_failure_rate=0.0
    )
    assert d2.requested_calls == 6
    
    # 5 available, 5 ringing -> 0 calls
    d3 = engine.calculate_pacing(
        available_agents=5, connected_calls=0, ringing_calls=5, wrap_up_agents=0,
        historical_answer_rate=0.4, avg_talk_time_sec=90, avg_ring_time_sec=20,
        provider_latency_sec=0.1, provider_failure_rate=0.0
    )
    assert d3.requested_calls == 0

def test_predictive_pacing_accounts_for_freeing_agents():
    engine = PredictivePacingEngine(confidence_factor=0.90)
    
    # 5 available, 20 connected, 100s talk time, 20s ring window.
    # Expected freeing = 20 * (20/100) = 4.0
    # Capacity = 5 + 4 = 9.0.
    # At 50% answer rate: raw calls = 9 / 0.5 = 18. Damped = 18 * 0.9 = 16 calls.
    decision = engine.calculate_pacing(
        available_agents=5,
        connected_calls=20,
        ringing_calls=0,
        wrap_up_agents=0,
        historical_answer_rate=0.50,
        avg_talk_time_sec=100.0,
        avg_ring_time_sec=20.0,
        provider_latency_sec=0.0,
        provider_failure_rate=0.0
    )
    
    assert decision.mode == DialingMode.PREDICTIVE
    assert decision.requested_calls >= 14
    assert decision.metrics["expected_freeing_agents"] == 4.0
    assert decision.metrics["projected_capacity"] == 9.0
    assert "Predictive model" in decision.rationale

def test_predictive_pacing_discounts_in_flight_ringing():
    engine = PredictivePacingEngine(confidence_factor=0.90)
    
    # Same as above, but 6 calls already ringing.
    # 6 ringing * 0.50 = 3 answers expected.
    # Unfilled capacity = 9.0 - 3.0 = 6.0.
    # Raw calls = 6.0 / 0.5 = 12. Damped = ~11 calls.
    decision = engine.calculate_pacing(
        available_agents=5,
        connected_calls=20,
        ringing_calls=6,
        wrap_up_agents=0,
        historical_answer_rate=0.50,
        avg_talk_time_sec=100.0,
        avg_ring_time_sec=20.0,
        provider_latency_sec=0.1,
        provider_failure_rate=0.0
    )
    
    assert decision.requested_calls < 14
    assert decision.metrics["in_flight_expected_answers"] == 3.0
