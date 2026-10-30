import math
from backend.app.models.enums import DialingMode
from backend.app.pacing.base import BasePacingEngine, PacingDecision

class PredictivePacingEngine(BasePacingEngine):
    """
    Predictive Pacing Engine:
    - Calculates safe overdialing based on Little's law, expected agent release rate,
      historical answer rate, provider latency, and ringing duration.
    - Yields higher agent utilization while providing explainable rationale.
    """
    def __init__(self, confidence_factor: float = 0.90, max_overdial_multiplier: float = 3.0):
        self.confidence_factor = confidence_factor
        self.max_overdial_multiplier = max_overdial_multiplier

    def calculate_pacing(
        self,
        available_agents: int,
        connected_calls: int,
        ringing_calls: int,
        wrap_up_agents: int,
        historical_answer_rate: float,
        avg_talk_time_sec: float,
        avg_ring_time_sec: float,
        provider_latency_sec: float,
        provider_failure_rate: float
    ) -> PacingDecision:
        # Effective ring window includes carrier latency
        ring_window = max(5.0, avg_ring_time_sec + provider_latency_sec)
        talk_time = max(10.0, avg_talk_time_sec)
        
        # Effective answer rate considering provider carrier failures
        effective_answer_rate = max(0.05, min(0.95, historical_answer_rate * (1.0 - provider_failure_rate)))

        # 1. Expected agents freeing up during ring window (Poisson departure rate: lambda = C_conn / T_talk)
        expected_free_from_connected = connected_calls * (ring_window / talk_time)
        # Wrap up agents are expected to become available quickly (say within ring_window)
        expected_free_from_wrap = wrap_up_agents * 0.8
        total_expected_freeing = expected_free_from_connected + expected_free_from_wrap

        # 2. Total capacity anticipated when calls placed right now answer
        projected_capacity = available_agents + total_expected_freeing

        # 3. Existing ringing calls expected to answer
        in_flight_expected_answers = ringing_calls * effective_answer_rate

        # 4. Net agent capacity remaining to be filled
        unfilled_capacity = max(0.0, projected_capacity - in_flight_expected_answers)

        # 5. Raw calls needed to produce unfilled_capacity answers
        raw_calls_needed = unfilled_capacity / effective_answer_rate

        # 6. Statistical variance discount (conservative factor to guard against answer bursts)
        damped_calls = raw_calls_needed * self.confidence_factor

        # 7. Engine-level sanity bound (max overdial relative to current available + active pool)
        capacity_base = max(1.0, float(available_agents) + float(wrap_up_agents) + (0.3 * connected_calls))
        max_engine_calls = int(capacity_base * self.max_overdial_multiplier)
        
        final_requested = max(0, min(int(round(damped_calls)), max_engine_calls))

        # Build detailed explainable metrics
        metrics = {
            "available_agents": available_agents,
            "connected_calls": connected_calls,
            "ringing_calls": ringing_calls,
            "wrap_up_agents": wrap_up_agents,
            "ring_window_sec": round(ring_window, 1),
            "avg_talk_time_sec": round(talk_time, 1),
            "historical_answer_rate": round(historical_answer_rate, 4),
            "effective_answer_rate": round(effective_answer_rate, 4),
            "expected_freeing_agents": round(total_expected_freeing, 2),
            "projected_capacity": round(projected_capacity, 2),
            "in_flight_expected_answers": round(in_flight_expected_answers, 2),
            "unfilled_capacity": round(unfilled_capacity, 2),
            "raw_calls_needed": round(raw_calls_needed, 2),
            "requested_calls": final_requested
        }

        rationale = (
            f"Predictive model: {available_agents} available agents + {total_expected_freeing:.1f} expected completions "
            f"in {ring_window:.1f}s ring window gives {projected_capacity:.1f} capacity. "
            f"With {ringing_calls} ringing calls ({in_flight_expected_answers:.1f} expected answers), "
            f"at {effective_answer_rate*100:.1f}% answer rate, requested {final_requested} call(s)."
        )

        return PacingDecision(
            mode=DialingMode.PREDICTIVE,
            requested_calls=final_requested,
            metrics=metrics,
            rationale=rationale
        )
