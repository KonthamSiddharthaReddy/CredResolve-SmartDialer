from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Agent, Borrower, Campaign, Call, SafetyDecisionAudit
from backend.app.models.enums import AgentState, BorrowerStatus, CallState, DialingMode, ProviderType
from backend.app.schemas import SystemMetricsResponse, SafetyDecisionAuditResponse
from backend.app.services.dialer_worker import DialerWorker, provider_a_instance, provider_b_instance

router = APIRouter(prefix="/dialer", tags=["Dialer"])

@router.post("/cycle")
def trigger_dialer_cycle(campaign_id: int = Query(1), db: Session = Depends(get_db)):
    result = DialerWorker.run_dialing_cycle(db, campaign_id)
    return result

@router.get("/metrics", response_model=SystemMetricsResponse)
def get_metrics(campaign_id: int = Query(1), db: Session = Depends(get_db)):
    campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
    if not campaign:
        # Default fallback values if no campaign created yet
        dialing_mode = DialingMode.PROGRESSIVE
        active_provider = ProviderType.PROVIDER_A
        answer_rate = 0.40
    else:
        dialing_mode = DialingMode(campaign.dialing_mode)
        active_provider = ProviderType(campaign.provider_type)
        answer_rate = campaign.historical_answer_rate

    # Agents breakdown
    total_agents = db.execute(select(func.count(Agent.id))).scalar() or 0
    available_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.AVAILABLE.value)).scalar() or 0
    reserved_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.RESERVED.value)).scalar() or 0
    dialing_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.DIALING.value)).scalar() or 0
    connected_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.CONNECTED.value)).scalar() or 0
    wrap_up_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.WRAP_UP.value)).scalar() or 0
    paused_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.PAUSED.value)).scalar() or 0
    offline_agents = db.execute(select(func.count(Agent.id)).where(Agent.status == AgentState.OFFLINE.value)).scalar() or 0

    active_agent_pool = max(1, total_agents - offline_agents - paused_agents)
    utilization = round((connected_agents / active_agent_pool) * 100.0, 1)

    # Calls breakdown
    queued_borrowers = db.execute(select(func.count(Borrower.id)).where(Borrower.status == BorrowerStatus.QUEUED.value)).scalar() or 0
    ringing_calls = db.execute(select(func.count(Call.id)).where(Call.status.in_([CallState.INITIATED.value, CallState.RINGING.value]))).scalar() or 0
    connected_calls = db.execute(select(func.count(Call.id)).where(Call.status == CallState.CONNECTED.value)).scalar() or 0
    completed_calls = db.execute(select(func.count(Call.id)).where(Call.status == CallState.COMPLETED.value)).scalar() or 0
    failed_calls = db.execute(select(func.count(Call.id)).where(Call.status == CallState.FAILED.value)).scalar() or 0
    abandoned_calls = db.execute(select(func.count(Call.id)).where(Call.is_abandoned.is_(True))).scalar() or 0

    total_resolved = connected_calls + completed_calls + abandoned_calls
    abandon_rate = round((abandoned_calls / total_resolved) * 100.0, 2) if total_resolved > 0 else 0.0

    # Last safety audit
    last_audit = (
        db.execute(select(SafetyDecisionAudit).where(SafetyDecisionAudit.campaign_id == campaign_id).order_by(SafetyDecisionAudit.id.desc()).limit(1))
        .scalar_one_or_none()
    )

    return SystemMetricsResponse(
        total_agents=total_agents,
        available_agents=available_agents,
        reserved_agents=reserved_agents,
        dialing_agents=dialing_agents,
        connected_agents=connected_agents,
        wrap_up_agents=wrap_up_agents,
        paused_agents=paused_agents,
        offline_agents=offline_agents,
        agent_utilization_rate=utilization,
        queued_borrowers=queued_borrowers,
        in_flight_calls=ringing_calls,
        ringing_calls=ringing_calls,
        connected_calls=connected_calls,
        completed_calls=completed_calls,
        failed_calls=failed_calls,
        abandoned_calls=abandoned_calls,
        abandon_rate=abandon_rate,
        current_dialing_mode=dialing_mode,
        active_provider=active_provider,
        provider_a_circuit=provider_a_instance.circuit_breaker.state,
        provider_b_circuit=provider_b_instance.circuit_breaker.state,
        estimated_answer_rate=round(answer_rate, 4),
        last_safety_decision=last_audit
    )

@router.get("/safety-audits", response_model=List[SafetyDecisionAuditResponse])
def list_safety_audits(
    campaign_id: int = Query(1),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    return (
        db.execute(
            select(SafetyDecisionAudit)
            .where(SafetyDecisionAudit.campaign_id == campaign_id)
            .order_by(SafetyDecisionAudit.id.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )
