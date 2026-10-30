import random
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
from sqlalchemy import select, update, func
from sqlalchemy.orm import Session
from backend.app.models import Agent, Borrower, Campaign, Call
from backend.app.models.enums import AgentState, BorrowerStatus, CallState, DialingMode, ProviderType
from backend.app.services.dialer_worker import DialerWorker, provider_a_instance, provider_b_instance
from backend.app.state_machines.agent_state_machine import AgentStateMachine
from backend.app.state_machines.call_state_machine import CallStateMachine
from backend.app.services.recovery_service import RecoveryService

class SimulationEngine:
    """
    Simulation Engine:
    - Supports Scenarios A, B, C, D
    - Drives time-compressed realistic call progression (RINGING -> ANSWERED -> CONNECTED -> COMPLETED / FAILED)
    - Provides interactive Chaos & Failure Injection
    - Computes real-time telemetry metrics
    """

    def __init__(self):
        self.is_running = False
        self.current_scenario = "SCENARIO_B"
        self.time_compression = 10.0  # 10x accelerated for realistic testing
        self.scenario_d_step = 0
        self.last_tick_time = time.time()

    def set_scenario(self, db: Session, scenario_name: str, campaign_id: int = 1) -> Dict[str, Any]:
        campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
        if not campaign:
            return {"error": "Campaign not found"}

        self.current_scenario = scenario_name.upper()

        if self.current_scenario == "SCENARIO_A":
            campaign.historical_answer_rate = 0.20
            campaign.avg_talk_time_seconds = 120.0
            campaign.avg_ring_time_seconds = 20.0
            provider_a_instance.base_latency_ms = 80.0
        elif self.current_scenario == "SCENARIO_B":
            campaign.historical_answer_rate = 0.50
            campaign.avg_talk_time_seconds = 90.0
            campaign.avg_ring_time_seconds = 15.0
            provider_a_instance.base_latency_ms = 100.0
        elif self.current_scenario == "SCENARIO_C":
            campaign.historical_answer_rate = 0.70
            campaign.avg_talk_time_seconds = 180.0
            campaign.avg_ring_time_seconds = 20.0
            provider_a_instance.base_latency_ms = 90.0
        elif self.current_scenario == "SCENARIO_D":
            # Dynamic volatile scenario
            campaign.historical_answer_rate = 0.35
            campaign.avg_talk_time_seconds = 100.0
            campaign.avg_ring_time_seconds = 18.0
            self.scenario_d_step = 0

        db.commit()
        return {
            "scenario": self.current_scenario,
            "answer_rate": campaign.historical_answer_rate,
            "avg_talk_time_sec": campaign.avg_talk_time_seconds,
            "avg_ring_time_sec": campaign.avg_ring_time_seconds
        }

    def inject_failure(self, db: Session, failure_type: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        params = params or {}
        ftype = failure_type.upper()

        if ftype == "DROP_AGENTS":
            # E.g. Drop 40 agents out of 100 (or 40% of available)
            count_to_drop = params.get("count", 40)
            available_agents = (
                db.execute(select(Agent).where(Agent.status == AgentState.AVAILABLE.value).limit(count_to_drop))
                .scalars()
                .all()
            )
            dropped = 0
            for a in available_agents:
                AgentStateMachine.transition(a, AgentState.OFFLINE, reason="Chaos: Sudden Agent Drop")
                dropped += 1
            db.commit()
            return {"status": "success", "action": "DROP_AGENTS", "dropped_count": dropped}

        elif ftype == "RESTORE_AGENTS":
            offline_agents = (
                db.execute(select(Agent).where(Agent.status == AgentState.OFFLINE.value))
                .scalars()
                .all()
            )
            restored = 0
            for a in offline_agents:
                AgentStateMachine.transition(a, AgentState.AVAILABLE, reason="Chaos: Agent Restored")
                restored += 1
            db.commit()
            return {"status": "success", "action": "RESTORE_AGENTS", "restored_count": restored}

        elif ftype == "PROVIDER_OUTAGE":
            provider_a_instance.force_outage = True
            provider_b_instance.force_outage = True
            provider_a_instance.circuit_breaker.trip()
            provider_b_instance.circuit_breaker.trip()
            return {"status": "success", "action": "PROVIDER_OUTAGE", "message": "Forced outage and tripped circuit breakers."}

        elif ftype == "RESTORE_PROVIDER":
            provider_a_instance.force_outage = False
            provider_b_instance.force_outage = False
            provider_a_instance.circuit_breaker.reset()
            provider_b_instance.circuit_breaker.reset()
            return {"status": "success", "action": "RESTORE_PROVIDER", "message": "Restored telecom providers and circuits."}

        elif ftype == "ANSWER_RATE_CRASH":
            # E.g. Crash answer rate from 70% to 10%
            new_rate = params.get("rate", 0.10)
            campaign = db.execute(select(Campaign).where(Campaign.id == 1)).scalar_one_or_none()
            if campaign:
                campaign.historical_answer_rate = new_rate
                db.commit()
            return {"status": "success", "action": "ANSWER_RATE_CRASH", "new_answer_rate": new_rate}

        elif ftype == "WORKER_CRASH":
            # Simulate worker crash: Reserve 3 agents and borrowers, but never dispatch, leaving stale locks
            candidates = (
                db.execute(select(Agent).where(Agent.status == AgentState.AVAILABLE.value).limit(3))
                .scalars()
                .all()
            )
            now = datetime.now(timezone.utc)
            crashed_count = 0
            for a in candidates:
                a.status = AgentState.RESERVED.value
                a.reserved_at = now
                a.version += 1
                crashed_count += 1
            db.commit()
            return {"status": "success", "action": "WORKER_CRASH", "crashed_reservations": crashed_count}

        elif ftype == "INJECT_DUPLICATE_WEBHOOK":
            # Find an active connected or answered call and send duplicate ANSWERED
            active_call = (
                db.execute(select(Call).where(Call.status.in_([CallState.CONNECTED.value, CallState.ANSWERED.value])).limit(1))
                .scalar_one_or_none()
            )
            if active_call:
                res = DialerWorker.process_call_answered(db, active_call.id)
                return {"status": "success", "action": "DUPLICATE_WEBHOOK", "call_id": active_call.id, "result": res}
            return {"status": "no_active_call", "message": "No active call found for duplicate injection."}

        elif ftype == "INJECT_OUT_OF_ORDER":
            # Find a ringing call and send COMPLETED before ANSWERED
            ringing_call = (
                db.execute(select(Call).where(Call.status == CallState.RINGING.value).limit(1))
                .scalar_one_or_none()
            )
            if ringing_call:
                res = DialerWorker.process_call_completed(db, ringing_call.id, talk_duration=12.0)
                return {"status": "success", "action": "OUT_OF_ORDER_WEBHOOK", "call_id": ringing_call.id, "result": res}
            return {"status": "no_ringing_call", "message": "No ringing call found for out-of-order injection."}

        return {"error": f"Unknown failure type: {failure_type}"}

    def tick(self, db: Session, campaign_id: int = 1) -> Dict[str, Any]:
        """
        Single simulation tick:
        1. Dynamically varies parameters in Scenario D
        2. Progresses in-flight ringing calls (RINGING -> ANSWERED or FAILED)
        3. Progresses connected calls (CONNECTED -> COMPLETED)
        4. Progresses wrap-up agents (WRAP_UP -> AVAILABLE)
        5. Triggers DialerWorker cycle to dial new calls
        6. Runs Janitor / Reaper for crash recovery
        """
        campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
        if not campaign or not campaign.is_active:
            return {"status": "inactive"}

        # 1. Scenario D dynamics (fluctuating conditions)
        if self.current_scenario == "SCENARIO_D":
            self.scenario_d_step += 1
            # Wave modulation: answer rate fluctuates between 15% and 65%
            import math
            wave = (math.sin(self.scenario_d_step * 0.15) + 1.0) / 2.0  # 0 to 1
            campaign.historical_answer_rate = 0.15 + (0.50 * wave)
            # Latency fluctuates between 100ms and 900ms
            provider_a_instance.base_latency_ms = 100.0 + (800.0 * (1.0 - wave))
            db.commit()

        # 2. Advance Ringing Calls (probabilistic answer or failure)
        ringing_calls = (
            db.execute(select(Call).where(Call.status == CallState.RINGING.value))
            .scalars()
            .all()
        )
        answer_rate = campaign.historical_answer_rate

        for call in ringing_calls:
            # Probability check per tick
            roll = random.random()
            if roll < answer_rate:
                # Call is answered!
                DialerWorker.process_call_answered(db, call.id)
            elif roll > 0.85:
                # Call failed / busy / no-answer
                CallStateMachine.transition(call, CallState.FAILED, failure_reason="NO_ANSWER_OR_BUSY")
                if call.agent_id:
                    agent = db.execute(select(Agent).where(Agent.id == call.agent_id)).scalar_one_or_none()
                    if agent:
                        AgentStateMachine.transition(agent, AgentState.AVAILABLE)
                if call.borrower_id:
                    borrower = db.execute(select(Borrower).where(Borrower.id == call.borrower_id)).scalar_one_or_none()
                    if borrower:
                        borrower.status = BorrowerStatus.FAILED.value
                db.commit()

        # 3. Advance Connected Calls (complete talk time)
        connected_calls = (
            db.execute(select(Call).where(Call.status == CallState.CONNECTED.value))
            .scalars()
            .all()
        )
        # Accelerated completion probability per tick: avg_talk_time compressed
        completion_prob = min(0.60, 1.0 / max(1.0, (campaign.avg_talk_time_seconds / self.time_compression)))
        for call in connected_calls:
            if random.random() < completion_prob:
                simulated_talk = campaign.avg_talk_time_seconds * random.uniform(0.7, 1.3)
                DialerWorker.process_call_completed(db, call.id, talk_duration=simulated_talk)

        # 4. Advance Wrap-up Agents to AVAILABLE
        wrap_up_agents = (
            db.execute(select(Agent).where(Agent.status == AgentState.WRAP_UP.value))
            .scalars()
            .all()
        )
        for agent in wrap_up_agents:
            if random.random() < 0.70:  # Rapid wrap up
                AgentStateMachine.transition(agent, AgentState.AVAILABLE)
        db.commit()

        # 5. Execute Next Dialer Cycle
        dialer_result = DialerWorker.run_dialing_cycle(db, campaign.id)

        # 6. Run Stale Reservation Janitor
        recovery_stats = RecoveryService.reap_stale_reservations(db)

        return {
            "status": "ticked",
            "scenario": self.current_scenario,
            "dialer_result": dialer_result,
            "recovery_stats": recovery_stats
        }

simulation_engine_instance = SimulationEngine()
