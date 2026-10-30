from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Call
from backend.app.models.enums import CallState
from backend.app.schemas import CallResponse

router = APIRouter(prefix="/calls", tags=["Calls"])

@router.get("", response_model=List[CallResponse])
def list_calls(
    status: Optional[CallState] = None,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    query = select(Call)
    if status:
        query = query.where(Call.status == status.value)
    query = query.order_by(Call.id.desc()).limit(limit)
    return db.execute(query).scalars().all()

@router.get("/active", response_model=List[CallResponse])
def list_active_calls(limit: int = Query(50, ge=1, le=200), db: Session = Depends(get_db)):
    active_states = [CallState.INITIATED.value, CallState.RINGING.value, CallState.ANSWERED.value, CallState.CONNECTED.value]
    query = select(Call).where(Call.status.in_(active_states)).order_by(Call.id.desc()).limit(limit)
    return db.execute(query).scalars().all()
