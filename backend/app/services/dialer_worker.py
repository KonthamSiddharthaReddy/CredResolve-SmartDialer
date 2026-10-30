import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.models import Agent, Borrower, Campaign, Call, SafetyDecisionAudit, ProviderAuditLog
from backend.app.models.enums import AgentState, BorrowerStatus, CallState, DialingMode, ProviderType, SafetyDecisionType, CircuitState
from backend.app.pacing.progressive import ProgressivePacingEngine
from backend.app.pacing.predictive import PredictivePacingEngine
from backend.app.pacing.safety_controller import SafetyController, SafetyEvaluation
from backend.app.telecom.provider_a import ProviderA
from backend.app.telecom.provider_b import ProviderB
from backend.app.state_machines.agent_state_machine import AgentStateMachine
from backend.app.state_machines.call_state_machine import CallStateMachine
from backend.app.services.allocation_service import AllocationService
from backend.app.services.recovery_service import RecoveryService

# Singleton providers and safety controller
provider_a_instance = ProviderA()
provider_b_instance = ProviderB()
safety_controller_instance = SafetyController()
progressive_engine = ProgressivePacingEngine()
predictive_engine = PredictivePacingEngine()

def get_provider(provider_type: ProviderType):
    if provider_type == ProviderType.PROVIDER_B:
        return provider_b_instance
    return provider_a_instance

class DialerWorker:
    """
    Core Dialer Orchestrator:
    Executes the campaign dialing loop:
    Campaign -> Pacing Engine -> Safety Controller -> Call Allocator -> Telecom Provider.
    """

    @staticmethod
    def run_dialing_cycle(db: Session, campaign_id: int) -> Dict[str, Any]:
        campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
        if not campaign or not campaign.is_active:
            return {"status": "inactive", "initiated_calls": 0}

        # 1. First run crash / stale reservation reaper (janitor hygiene)
        RecoveryService.reap_stale_reservations(db)

        # 2. Gather live operational metrics
        available_agents = db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentState.AVAILABLE.value)
        ).scalar() or 0

        reserved_agents = db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentState.RESERVED.value)
        ).scalar() or 0

        dialing_agents = db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentState.DIALING.value)
        ).scalar() or 0

        connected_calls = db.execute(
            select(func.count(Call.id)).where(Call.status == CallState.CONNECTED.value)
        ).scalar() or 0

        ringing_calls = db.execute(
            select(func.count(Call.id)).where(Call.status.in_([CallState.INITIATED.value, CallState.RINGING.value]))
        ).scalar() or 0

        wrap_up_agents = db.execute(
            select(func.count(Agent.id)).where(Agent.status == AgentState.WRAP_UP.value)
        ).scalar() or 0

        # Calculate recent abandonment rate (last 100 calls)
        recent_calls = (
            db.execute(
                select(Call)
                .where(Call.status.in_([CallState.COMPLETED.value, CallState.FAILED.value]))
                .order_by(Call.id.desc())
                .limit(100)
            )
            .scalars()
            .all()
        )
        recent_total = len(recent_calls)
        recent_abandons = sum(1 for c in recent_calls if c.is_abandoned)
        recent_abandon_rate = (recent_abandons / recent_total) if recent_total > 0 else 0.0

        # Dynamic answer rate calculation
        if recent_total >= 10:
            answered_count = sum(1 for c in recent_calls if c.answered_at is not None or c.status == CallState.COMPLETED.value)
            estimated_answer_rate = answered_count / recent_total
        else:
            estimated_answer_rate = campaign.historical_answer_rate

        # Provider health metrics
        provider = get_provider(ProviderType(campaign.provider_type))
        health = provider.get_health()
        circuit_state = provider.circuit_breaker.state
        provider_failure_rate = health["circuit"]["failure_rate"]
        provider_latency_sec = health["avg_latency_ms"] / 1000.0

        # 3. Pacing Engine Computation
        mode = DialingMode(campaign.dialing_mode)
        if mode == DialingMode.PROGRESSIVE:
            pacing_decision = progressive_engine.calculate_pacing(
                available_agents=available_agents,
                connected_calls=connected_calls,
                ringing_calls=ringing_calls,
                wrap_up_agents=wrap_up_agents,
                historical_answer_rate=estimated_answer_rate,
                avg_talk_time_sec=campaign.avg_talk_time_sec if hasattr(campaign, 'avg_talk_time_sec') else campaign.avg_talk_time_seconds,
                avg_ring_time_sec=campaign.avg_ring_time_sec if hasattr(campaign, 'avg_ring_time_sec') else campaign.avg_ring_time_seconds,
                provider_latency_sec=provider_latency_sec,
                provider_failure_rate=provider_failure_rate
            )
        else:
            pacing_decision = predictive_engine.calculate_pacing(
                available_agents=available_agents,
                connected_calls=connected_calls,
                ringing_calls=ringing_calls,
                wrap_up_agents=wrap_up_agents,
                historical_answer_rate=estimated_answer_rate,
                avg_talk_time_sec=campaign.avg_talk_time_seconds,
                avg_ring_time_sec=campaign.avg_ring_time_seconds,
                provider_latency_sec=provider_latency_sec,
                provider_failure_rate=provider_failure_rate
            )

        # 4. Mandatory Safety Controller Evaluation (Cannot be bypassed)
        safety_eval = safety_controller_instance.evaluate(
            pacing_decision=pacing_decision,
            available_agents=available_agents,
            ringing_calls=ringing_calls,
            connected_calls=connected_calls,
            wrap_up_agents=wrap_up_agents,
            circuit_state=circuit_state,
            provider_failure_rate=provider_failure_rate,
            recent_abandon_rate=recent_abandon_rate,
            recent_abandon_count=recent_abandons,
            current_answer_rate=estimated_answer_rate
        )

        # 5. Persist Safety Audit Record
        now = datetime.now(timezone.utc)
        audit = SafetyDecisionAudit(
            campaign_id=campaign.id,
            timestamp=now,
            dialing_mode=mode.value if not safety_eval.is_fallback else DialingMode.PROGRESSIVE.value,
            requested_calls=safety_eval.requested_calls,
            approved_calls=safety_eval.approved_calls,
            decision_type=safety_eval.decision_type.value,
            rationale=safety_eval.rationale,
            available_agents=available_agents,
            ringing_calls=ringing_calls,
            connected_calls=connected_calls,
            wrap_up_agents=wrap_up_agents,
            answer_rate_used=estimated_answer_rate,
            expected_free_agents=pacing_decision.metrics.get("expected_freeing_agents", 0.0),
            provider_health_status=circuit_state.value
        )
        db.add(audit)
        db.commit()

        # 6. Call Allocator: Execute Approved Calls
        calls_to_initiate = safety_eval.approved_calls
        initiated_call_ids: List[int] = []

        for _ in range(calls_to_initiate):
            # Borrower allocation
            borrower = AllocationService.reserve_next_queued_borrower(db, campaign.id)
            if not borrower:
                # Queue exhausted
                break

            # Agent allocation: In progressive or when agent is available, reserve upfront
            agent = None
            if mode == DialingMode.PROGRESSIVE or available_agents > 0:
                agent = AllocationService.reserve_next_available_agent(db)
                if not agent and mode == DialingMode.PROGRESSIVE:
                    # In progressive mode, if agent reservation fails, release borrower and stop
                    AllocationService.release_borrower_to_queued(db, borrower.id)
                    break
                if agent:
                    available_agents = max(0, available_agents - 1)

            # Generate unique idempotency key
            idempotency_key = f"camp-{campaign.id}-b-{borrower.id}-ts-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"

            # Create Call in RESERVED state
            call = Call(
                idempotency_key=idempotency_key,
                campaign_id=campaign.id,
                borrower_id=borrower.id,
                agent_id=agent.id if agent else None,
                provider_type=campaign.provider_type,
                status=CallState.RESERVED.value,
                reserved_at=now,
                created_at=now
            )
            db.add(call)
            db.commit()
            db.refresh(call)

            if agent:
                agent.current_call_id = call.id
                agent.status = AgentState.DIALING.value
                db.commit()

            borrower.status = BorrowerStatus.DIALING.value
            db.commit()

            # Mark Call INITIATED
            CallStateMachine.transition(call, CallState.INITIATED)
            db.commit()

            # Dispatch to provider synchronously or record for async execution
            # Call provider synchronously in this worker step
            import asyncio
            try:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and loop.is_running():
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        res = pool.submit(asyncio.run, provider.initiate_call(call.id, borrower.phone, idempotency_key)).result()
                else:
                    res = asyncio.run(provider.initiate_call(call.id, borrower.phone, idempotency_key))
            except Exception as e:
                res = asyncio.run(provider.initiate_call(call.id, borrower.phone, idempotency_key))

            if res.success:
                call.provider_call_id = res.provider_call_id
                CallStateMachine.transition(call, CallState.RINGING)
                db.commit()
                initiated_call_ids.append(call.id)
            else:
                # Provider rejected or failed initiation
                call.failure_reason = res.error_message
                CallStateMachine.transition(call, CallState.FAILED, failure_reason=res.error_message)
                # Rollback borrower & agent
                AllocationService.release_borrower_to_queued(db, borrower.id)
                if agent:
                    AllocationService.release_agent_to_available(db, agent.id)
                db.commit()

        return {
            "status": "success",
            "campaign_id": campaign.id,
            "mode": mode.value,
            "safety_decision": safety_eval.decision_type.value,
            "safety_rationale": safety_eval.rationale,
            "approved_calls": safety_eval.approved_calls,
            "initiated_calls_count": len(initiated_call_ids),
            "initiated_call_ids": initiated_call_ids
        }

    @staticmethod
    def process_call_answered(db: Session, call_id: int) -> Dict[str, Any]:
        """
        Processes ANSWERED event from provider.
        Bridges with reserved agent or dynamically finds one in predictive mode.
        If no agent is available, handles ABANDONED call!
        """
        call = db.execute(select(Call).where(Call.id == call_id)).scalar_one_or_none()
        if not call:
            return {"status": "error", "message": "Call not found"}

        # Check call state machine
        trans_result = CallStateMachine.transition(call, CallState.ANSWERED)
        db.commit()

        if trans_result.is_duplicate:
            return {"status": "duplicate", "message": trans_result.message}
        if trans_result.is_stale:
            return {"status": "stale", "message": trans_result.message}

        # Agent bridging
        agent = None
        if call.agent_id:
            agent = db.execute(select(Agent).where(Agent.id == call.agent_id)).scalar_one_or_none()

        if not agent:
            # Speculative predictive call answered: locate an available agent
            agent = AllocationService.reserve_next_available_agent(db)
            if agent:
                call.agent_id = agent.id
                agent.current_call_id = call.id
                db.commit()

        if agent:
            # Connect agent and call
            AgentStateMachine.transition(agent, AgentState.CONNECTED)
            CallStateMachine.transition(call, CallState.CONNECTED)
            db.commit()
            return {"status": "connected", "call_id": call.id, "agent_id": agent.id}
        else:
            # No agent available -> Compliance Abandonment!
            call.is_abandoned = True
            CallStateMachine.transition(call, CallState.FAILED, failure_reason="ABANDONED_CALL: No agent available upon borrower answer")
            db.commit()
            return {"status": "abandoned", "call_id": call.id, "message": "Call abandoned due to agent exhaustion"}

    @staticmethod
    def process_call_completed(db: Session, call_id: int, talk_duration: float = None) -> Dict[str, Any]:
        """
        Processes COMPLETED event from provider.
        Cleans up call, agent (moves to WRAP_UP), and borrower.
        """
        call = db.execute(select(Call).where(Call.id == call_id)).scalar_one_or_none()
        if not call:
            return {"status": "error", "message": "Call not found"}

        trans_result = CallStateMachine.transition(call, CallState.COMPLETED)
        if talk_duration:
            call.talk_duration_seconds = talk_duration
        db.commit()

        if trans_result.is_duplicate or trans_result.is_stale:
            return {"status": "ignored", "message": trans_result.message}

        # Release agent to WRAP_UP or AVAILABLE
        if call.agent_id:
            agent = db.execute(select(Agent).where(Agent.id == call.agent_id)).scalar_one_or_none()
            if agent and agent.status in {AgentState.CONNECTED.value, AgentState.DIALING.value, AgentState.RESERVED.value}:
                agent.total_calls_handled += 1
                agent.total_talk_time_seconds += (call.talk_duration_seconds or 0.0)
                AgentStateMachine.transition(agent, AgentState.WRAP_UP)
                db.commit()

        # Update borrower status to COMPLETED
        if call.borrower_id:
            borrower = db.execute(select(Borrower).where(Borrower.id == call.borrower_id)).scalar_one_or_none()
            if borrower:
                borrower.status = BorrowerStatus.COMPLETED.value
                db.commit()

        return {"status": "completed", "call_id": call.id}
