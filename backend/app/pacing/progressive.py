from backend.app.models.enums import DialingMode
from backend.app.pacing.base import BasePacingEngine, PacingDecision

class ProgressivePacingEngine(BasePacingEngine):
    """
    Progressive Dialer:
    - Exactly 1 available agent receives at most 1 outbound call.
    - Never allocates more calls than free available agents.
    - Highly predictable, safe, zero speculative risk.
    """
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
        # Net available capacity considering already ringing calls
        net_available = max(0, available_agents - ringing_calls)
        requested = net_available

        metrics = {
            "available_agents": available_agents,
            "connected_calls": connected_calls,
            "ringing_calls": ringing_calls,
            "wrap_up_agents": wrap_up_agents,
            "historical_answer_rate": round(historical_answer_rate, 4),
            "net_available_agents": net_available,
            "requested_calls": requested
        }

        rationale = (
            f"Progressive mode 1:1 policy: {available_agents} available agent(s) minus "
            f"{ringing_calls} already ringing call(s) yields {requested} call(s) requested."
        )

        return PacingDecision(
            mode=DialingMode.PROGRESSIVE,
            requested_calls=requested,
            metrics=metrics,
            rationale=rationale
        )
