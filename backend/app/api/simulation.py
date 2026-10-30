from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, delete
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Agent, Borrower, Campaign, Call, SafetyDecisionAudit, ProviderAuditLog
from backend.app.models.enums import AgentState, BorrowerStatus, DialingMode, ProviderType
from backend.app.schemas import FailureInjectionRequest
from backend.app.services.simulation_engine import simulation_engine_instance
from backend.app.services.recovery_service import RecoveryService

router = APIRouter(prefix="/simulation", tags=["Simulation"])

@router.post("/scenario")
def set_scenario(name: str = Query("SCENARIO_B"), campaign_id: int = Query(1), db: Session = Depends(get_db)):
    return simulation_engine_instance.set_scenario(db, name, campaign_id)

@router.post("/tick")
def tick_simulation(ticks: int = Query(1, ge=1, le=50), campaign_id: int = Query(1), db: Session = Depends(get_db)):
    results = []
    for _ in range(ticks):
        res = simulation_engine_instance.tick(db, campaign_id)
        results.append(res)
    return {"ticks_executed": ticks, "last_result": results[-1]}

@router.post("/failure")
def inject_failure(req: FailureInjectionRequest, db: Session = Depends(get_db)):
    return simulation_engine_instance.inject_failure(db, req.type, req.params)

@router.post("/recover")
def trigger_recovery(db: Session = Depends(get_db)):
    stale_res = RecoveryService.reap_stale_reservations(db)
    orphaned_calls = RecoveryService.reap_orphaned_calls(db)
    return {
        "status": "recovery_complete",
        "stale_reservations": stale_res,
        "orphaned_calls": orphaned_calls
    }

@router.post("/reset")
def reset_simulation(
    num_agents: int = Query(60, ge=10, le=200),
    num_borrowers: int = Query(250, ge=20, le=1000),
    db: Session = Depends(get_db)
):
    """
    Cleans database and seeds fresh agents, queued borrowers, and campaign.
    """
    db.execute(delete(Call))
    db.execute(delete(SafetyDecisionAudit))
    db.execute(delete(ProviderAuditLog))
    db.execute(delete(Agent))
    db.execute(delete(Borrower))
    db.execute(delete(Campaign))
    db.commit()

    # 1. Create Default Campaign
    campaign = Campaign(
        id=1,
        name="Credit Recovery Q4",
        dialing_mode=DialingMode.PROGRESSIVE.value,
        provider_type=ProviderType.PROVIDER_A.value,
        is_active=True,
        target_abandon_rate=0.01,
        avg_talk_time_seconds=90.0,
        avg_ring_time_seconds=15.0,
        historical_answer_rate=0.50
    )
    db.add(campaign)
    db.commit()

    # 2. Seed Agents
    agents = [
        Agent(name=f"Agent-{i:03d}", status=AgentState.AVAILABLE.value)
        for i in range(1, num_agents + 1)
    ]
    db.add_all(agents)

    # 3. Seed Borrowers
    borrowers = [
        Borrower(
            name=f"Borrower-{i:04d}",
            phone=f"+9198765{i:05d}",
            status=BorrowerStatus.QUEUED.value,
            priority=(3 if i % 10 == 0 else (2 if i % 3 == 0 else 1)),
            campaign_id=1
        )
        for i in range(1, num_borrowers + 1)
    ]
    db.add_all(borrowers)
    db.commit()

    # Reset simulation scenario
    simulation_engine_instance.set_scenario(db, "SCENARIO_B", campaign_id=1)

    return {
        "status": "reset_successful",
        "seeded_agents": num_agents,
        "seeded_borrowers": num_borrowers,
        "campaign_id": 1,
        "scenario": "SCENARIO_B"
    }
