from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Call, ProviderAuditLog
from backend.app.models.enums import CallState
from backend.app.schemas import ProviderWebhookEvent
from backend.app.services.dialer_worker import DialerWorker
from backend.app.state_machines.call_state_machine import CallStateMachine

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

@router.post("/provider")
def handle_provider_webhook(event: ProviderWebhookEvent, db: Session = Depends(get_db)):
    # Locate call by provider_call_id
    call = (
        db.execute(select(Call).where(Call.provider_call_id == event.provider_call_id))
        .scalar_one_or_none()
    )
    if not call:
        raise HTTPException(status_code=404, detail=f"Call with provider_call_id {event.provider_call_id} not found")

    event_type = event.event_type.upper()
    is_duplicate = False
    is_out_of_order = False
    details = f"Received webhook: {event_type}"

    if event_type == "RINGING":
        res = CallStateMachine.transition(call, CallState.RINGING)
        is_duplicate = res.is_duplicate
        is_out_of_order = res.is_out_of_order
        details = res.message
        db.commit()

    elif event_type == "ANSWERED":
        res = DialerWorker.process_call_answered(db, call.id)
        if res.get("status") == "duplicate":
            is_duplicate = True
        details = str(res)

    elif event_type == "COMPLETED":
        res = DialerWorker.process_call_completed(db, call.id, talk_duration=event.talk_duration)
        if res.get("status") == "ignored":
            is_duplicate = True
        details = str(res)

    elif event_type == "FAILED":
        res = CallStateMachine.transition(call, CallState.FAILED, failure_reason=event.reason or "Provider Webhook Failed")
        is_duplicate = res.is_duplicate
        details = res.message
        db.commit()

    # Log to ProviderAuditLog
    audit = ProviderAuditLog(
        provider_name=call.provider_type,
        event_type=event_type,
        call_id=call.id,
        provider_call_id=event.provider_call_id,
        idempotency_key=event.idempotency_key,
        is_duplicate=is_duplicate,
        is_out_of_order=is_out_of_order,
        details=details
    )
    db.add(audit)
    db.commit()

    return {
        "status": "processed",
        "call_id": call.id,
        "is_duplicate": is_duplicate,
        "is_out_of_order": is_out_of_order,
        "details": details
    }
