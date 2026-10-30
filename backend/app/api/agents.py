from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Agent
from backend.app.models.enums import AgentState
from backend.app.schemas import AgentResponse, AgentCreate, AgentStateUpdateRequest
from backend.app.state_machines.agent_state_machine import AgentStateMachine, InvalidAgentStateTransitionException

router = APIRouter(prefix="/agents", tags=["Agents"])

@router.get("", response_model=List[AgentResponse])
def list_agents(
    status: Optional[AgentState] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    query = select(Agent)
    if status:
        query = query.where(Agent.status == status.value)
    query = query.order_by(Agent.id.asc()).limit(limit)
    return db.execute(query).scalars().all()

@router.post("", response_model=AgentResponse)
def create_agent(agent_in: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(name=agent_in.name, status=AgentState.AVAILABLE.value)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent

@router.patch("/{agent_id}/status", response_model=AgentResponse)
def update_agent_status(
    agent_id: int,
    req: AgentStateUpdateRequest,
    db: Session = Depends(get_db)
):
    agent = db.execute(select(Agent).where(Agent.id == agent_id)).scalar_one_or_none()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")

    try:
        AgentStateMachine.transition(agent, req.status, reason="Manual user update via API")
        agent.version += 1
        db.commit()
        db.refresh(agent)
        return agent
    except InvalidAgentStateTransitionException as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/seed")
def seed_agents(count: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    """Seed N agents in AVAILABLE state"""
    existing = db.execute(select(Agent)).scalars().all()
    start_index = len(existing) + 1
    new_agents = []
    for i in range(start_index, start_index + count):
        agent = Agent(name=f"Agent-{i:03d}", status=AgentState.AVAILABLE.value)
        new_agents.append(agent)
    db.add_all(new_agents)
    db.commit()
    return {"message": f"Successfully seeded {count} agents", "total_agents": start_index + count - 1}
