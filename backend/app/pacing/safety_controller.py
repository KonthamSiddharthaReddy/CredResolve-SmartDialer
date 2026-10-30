from dataclasses import dataclass
from typing import Dict, Any, Optional
from backend.app.models.enums import DialingMode, SafetyDecisionType, CircuitState
from backend.app.pacing.base import PacingDecision

@dataclass
class SafetyEvaluation:
    decision_type: SafetyDecisionType
    approved_calls: int
    requested_calls: int
    rationale: str
    is_fallback: bool = False
    metrics_snapshot: Dict[str, Any] = None

class SafetyController:
    """
    Independent Safety Controller:
    - Sits strictly between Pacing Engine and Call Allocator.
    - Cannot be bypassed or disabled by pacing engines or campaign configs.
    - Decides whether requested calls are APPROVED, REDUCED, REJECTED,
      or forced to FALLBACK_PROGRESSIVE.
    - Enforces regulatory compliance (0% abandoned calls target, max 1% threshold).
    """
    def __init__(
        self,
        max_overdial_multiplier: float = 3.0,
        max_abandon_rate: float = 0.01,
        min_answer_rate_threshold: float = 0.10
    ):
        self.max_overdial_multiplier = max_overdial_multiplier
        self.max_abandon_rate = max_abandon_rate
        self.min_answer_rate_threshold = min_answer_rate_threshold

    def evaluate(
        self,
        pacing_decision: PacingDecision,
        available_agents: int,
        ringing_calls: int,
        connected_calls: int,
        wrap_up_agents: int,
        circuit_state: CircuitState,
        provider_failure_rate: float,
        recent_abandon_rate: float,
        recent_abandon_count: int,
        current_answer_rate: float
    ) -> SafetyEvaluation:
        requested = pacing_decision.requested_calls
        mode = pacing_decision.mode

        snapshot = {
            "mode": mode.value,
            "requested_calls": requested,
            "available_agents": available_agents,
            "ringing_calls": ringing_calls,
            "connected_calls": connected_calls,
            "wrap_up_agents": wrap_up_agents,
            "circuit_state": circuit_state.value,
            "provider_failure_rate": round(provider_failure_rate, 4),
            "recent_abandon_rate": round(recent_abandon_rate, 4),
            "recent_abandon_count": recent_abandon_count,
            "current_answer_rate": round(current_answer_rate, 4)
        }

        # -------------------------------------------------------------
        # Rule 1: Zero Agent Guard
        # -------------------------------------------------------------
        if available_agents == 0 and wrap_up_agents == 0 and connected_calls == 0:
            return SafetyEvaluation(
                decision_type=SafetyDecisionType.REJECTED,
                approved_calls=0,
                requested_calls=requested,
                rationale="Safety rejected: zero available or active agents in pool.",
                metrics_snapshot=snapshot
            )

        # -------------------------------------------------------------
        # Rule 2: Provider Health & Circuit Breaker Check
        # -------------------------------------------------------------
        if circuit_state in {CircuitState.OPEN, CircuitState.HALF_OPEN}:
            if mode == DialingMode.PREDICTIVE:
                # Force fallback to progressive with 1-call limit if half-open, else 0
                approved = min(1, available_agents) if circuit_state == CircuitState.HALF_OPEN else 0
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.FALLBACK_PROGRESSIVE if approved > 0 else SafetyDecisionType.REJECTED,
                    approved_calls=approved,
                    requested_calls=requested,
                    rationale=f"Safety fallback: Provider circuit is {circuit_state.value}. Speculative dialing prohibited.",
                    is_fallback=True,
                    metrics_snapshot=snapshot
                )
            else:
                approved = 1 if (circuit_state == CircuitState.HALF_OPEN and available_agents > 0) else 0
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.REDUCED if approved < requested else SafetyDecisionType.REJECTED,
                    approved_calls=approved,
                    requested_calls=requested,
                    rationale=f"Safety throttle: Provider circuit is {circuit_state.value}.",
                    metrics_snapshot=snapshot
                )

        if provider_failure_rate >= 0.30:
            if mode == DialingMode.PREDICTIVE:
                net_free = max(0, available_agents - ringing_calls)
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.FALLBACK_PROGRESSIVE,
                    approved_calls=net_free,
                    requested_calls=requested,
                    rationale=f"Safety fallback: Provider failure rate high ({provider_failure_rate*100:.1f}%). Falling back to progressive 1:1 mode.",
                    is_fallback=True,
                    metrics_snapshot=snapshot
                )

        # -------------------------------------------------------------
        # Rule 3: Compliance Protection Against Abandoned Calls
        # -------------------------------------------------------------
        if recent_abandon_count > 0 or recent_abandon_rate > self.max_abandon_rate:
            if mode == DialingMode.PREDICTIVE:
                # Immediate fallback to progressive mode
                safe_progressive = max(0, available_agents - ringing_calls)
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.FALLBACK_PROGRESSIVE,
                    approved_calls=safe_progressive,
                    requested_calls=requested,
                    rationale=(
                        f"Safety fallback: Abandoned call threshold exceeded "
                        f"({recent_abandon_count} abandoned calls, {recent_abandon_rate*100:.2f}%). "
                        f"Predictive disabled for compliance safety; progressive mode enforced."
                    ),
                    is_fallback=True,
                    metrics_snapshot=snapshot
                )

        # -------------------------------------------------------------
        # Rule 4: Answer Rate Crash Protection
        # -------------------------------------------------------------
        if current_answer_rate < self.min_answer_rate_threshold and mode == DialingMode.PREDICTIVE:
            safe_progressive = max(0, available_agents - ringing_calls)
            return SafetyEvaluation(
                decision_type=SafetyDecisionType.FALLBACK_PROGRESSIVE,
                approved_calls=safe_progressive,
                requested_calls=requested,
                rationale=(
                    f"Safety fallback: Answer rate collapsed to {current_answer_rate*100:.1f}% "
                    f"(below {self.min_answer_rate_threshold*100:.0f}% threshold). Fallback to progressive to avoid queue saturation."
                ),
                is_fallback=True,
                metrics_snapshot=snapshot
            )

        # -------------------------------------------------------------
        # Rule 5: Sudden Agent Availability Drop Guard
        # -------------------------------------------------------------
        # If in-flight ringing calls already match or exceed available agents,
        # we cannot safely add more calls even if predictive model thinks agents will finish.
        if ringing_calls >= available_agents and available_agents > 0 and mode == DialingMode.PREDICTIVE:
            # Only allow extra calls if there is substantial connected call turnover expected
            if connected_calls < available_agents:
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.REJECTED,
                    approved_calls=0,
                    requested_calls=requested,
                    rationale=f"Safety rejected: {ringing_calls} in-flight calls already cover {available_agents} available agent(s).",
                    metrics_snapshot=snapshot
                )

        # -------------------------------------------------------------
        # Rule 6: Mode-Specific Capacity Limits
        # -------------------------------------------------------------
        if mode == DialingMode.PROGRESSIVE:
            # Deterministic progressive guarantee: never more calls than available agents
            progressive_ceiling = max(0, available_agents - ringing_calls)
            if requested > progressive_ceiling:
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.REDUCED,
                    approved_calls=progressive_ceiling,
                    requested_calls=requested,
                    rationale=f"Safety progressive ceiling: Clamped {requested} to {progressive_ceiling} available agent slot(s).",
                    metrics_snapshot=snapshot
                )
            elif requested <= 0:
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.REJECTED,
                    approved_calls=0,
                    requested_calls=requested,
                    rationale="Safety: zero capacity available.",
                    metrics_snapshot=snapshot
                )
            else:
                return SafetyEvaluation(
                    decision_type=SafetyDecisionType.APPROVED,
                    approved_calls=requested,
                    requested_calls=requested,
                    rationale=f"Safety approved progressive: {requested} call(s) mapped 1:1 to available agents.",
                    metrics_snapshot=snapshot
                )

        # Predictive Mode Hard Maximum Ceiling
        # Total in-flight cannot exceed multiplier of available + expected wrap-up
        capacity_base = max(1.0, float(available_agents) + float(wrap_up_agents) + (0.4 * connected_calls))
        hard_max_calls = int(capacity_base * self.max_overdial_multiplier)
        net_max_to_dial = max(0, hard_max_calls - ringing_calls)

        if requested > net_max_to_dial:
            approved = net_max_to_dial
            return SafetyEvaluation(
                decision_type=SafetyDecisionType.REDUCED if approved > 0 else SafetyDecisionType.REJECTED,
                approved_calls=approved,
                requested_calls=requested,
                rationale=f"Safety capacity cap: Reduced requested {requested} to {approved} (hard safety multiplier ceiling {self.max_overdial_multiplier}x).",
                metrics_snapshot=snapshot
            )

        if requested <= 0:
            return SafetyEvaluation(
                decision_type=SafetyDecisionType.REJECTED,
                approved_calls=0,
                requested_calls=requested,
                rationale="Safety: No call initiation required at this step.",
                metrics_snapshot=snapshot
            )

        return SafetyEvaluation(
            decision_type=SafetyDecisionType.APPROVED,
            approved_calls=requested,
            requested_calls=requested,
            rationale=f"Safety approved: {requested} call(s) safely within regulatory risk parameters.",
            metrics_snapshot=snapshot
        )
