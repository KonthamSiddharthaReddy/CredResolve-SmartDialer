from datetime import datetime, timezone
from typing import Tuple
from backend.app.models.enums import CallState

class InvalidCallStateTransitionException(Exception):
    def __init__(self, from_state: CallState, to_state: CallState, call_id: int, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.call_id = call_id
        self.reason = reason
        super().__init__(
            f"Invalid Call transition for Call #{call_id}: {from_state.value} -> {to_state.value}. {reason}".strip()
        )

TERMINAL_STATES = {CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED}

VALID_CALL_TRANSITIONS = {
    CallState.QUEUED: {CallState.RESERVED, CallState.CANCELLED},
    CallState.RESERVED: {CallState.INITIATED, CallState.CANCELLED, CallState.FAILED},
    CallState.INITIATED: {CallState.RINGING, CallState.ANSWERED, CallState.FAILED, CallState.CANCELLED, CallState.COMPLETED},
    CallState.RINGING: {CallState.ANSWERED, CallState.FAILED, CallState.CANCELLED, CallState.COMPLETED},
    CallState.ANSWERED: {CallState.CONNECTED, CallState.COMPLETED, CallState.FAILED, CallState.CANCELLED},
    CallState.CONNECTED: {CallState.COMPLETED, CallState.FAILED},
    CallState.COMPLETED: set(),
    CallState.FAILED: set(),
    CallState.CANCELLED: set(),
}

class CallTransitionResult:
    def __init__(self, success: bool, is_duplicate: bool = False, is_out_of_order: bool = False, is_stale: bool = False, message: str = ""):
        self.success = success
        self.is_duplicate = is_duplicate
        self.is_out_of_order = is_out_of_order
        self.is_stale = is_stale
        self.message = message

class CallStateMachine:
    @staticmethod
    def transition(call, to_state: CallState, failure_reason: str = None) -> CallTransitionResult:
        current_state = CallState(call.status)
        now = datetime.now(timezone.utc)

        # 1. Duplicate event detection
        if current_state == to_state:
            return CallTransitionResult(
                success=True,
                is_duplicate=True,
                message=f"Duplicate event: Call #{call.id} is already in state {to_state.value}"
            )

        # Duplicate/redundant pre-answer events when call has already connected
        if to_state == CallState.ANSWERED and current_state == CallState.CONNECTED:
            return CallTransitionResult(
                success=True,
                is_duplicate=True,
                message=f"Duplicate event: Call #{call.id} is already CONNECTED"
            )
        if to_state in {CallState.RINGING, CallState.INITIATED} and current_state in {CallState.ANSWERED, CallState.CONNECTED}:
            return CallTransitionResult(
                success=True,
                is_duplicate=True,
                message=f"Duplicate event: Call #{call.id} has already progressed to {current_state.value}"
            )

        # 2. Terminal state handling: trailing carrier events vs illegal transitions
        if current_state in TERMINAL_STATES:
            # Trailing carrier events on terminated call are stale and safe to ignore
            if to_state in {CallState.INITIATED, CallState.RINGING, CallState.ANSWERED, CallState.COMPLETED}:
                return CallTransitionResult(
                    success=False,
                    is_stale=True,
                    message=f"Stale event ignored: Call #{call.id} is already in terminal state {current_state.value}"
                )
            raise InvalidCallStateTransitionException(current_state, to_state, call.id, "Cannot transition from terminal state")

        # 3. Out-of-order handling: e.g. COMPLETED arriving while in INITIATED or RINGING
        is_out_of_order = False
        if to_state == CallState.COMPLETED and current_state in {CallState.INITIATED, CallState.RINGING}:
            is_out_of_order = True

        # 4. Check transition validity
        if to_state not in VALID_CALL_TRANSITIONS.get(current_state, set()):
            raise InvalidCallStateTransitionException(current_state, to_state, call.id, "Transition not allowed by state machine")

        # Apply transition
        call.status = to_state.value
        if to_state == CallState.RESERVED:
            call.reserved_at = now
        elif to_state == CallState.INITIATED:
            call.initiated_at = now
        elif to_state == CallState.RINGING:
            call.ringing_at = now
        elif to_state == CallState.ANSWERED:
            call.answered_at = now
            if call.ringing_at:
                call.ring_duration_seconds = max(0.0, (now - call.ringing_at.replace(tzinfo=timezone.utc) if call.ringing_at.tzinfo is None else now - call.ringing_at).total_seconds())
        elif to_state == CallState.CONNECTED:
            call.connected_at = now
        elif to_state == CallState.COMPLETED:
            call.completed_at = now
            if call.connected_at:
                c_at = call.connected_at.replace(tzinfo=timezone.utc) if call.connected_at.tzinfo is None else call.connected_at
                call.talk_duration_seconds = max(0.0, (now - c_at).total_seconds())
        elif to_state == CallState.FAILED:
            call.completed_at = now
            call.failure_reason = failure_reason or "Call failed"

        return CallTransitionResult(
            success=True,
            is_duplicate=False,
            is_out_of_order=is_out_of_order,
            message=f"Call #{call.id} moved from {current_state.value} to {to_state.value}"
        )
