from datetime import datetime, timezone
from backend.app.models.enums import AgentState

class InvalidAgentStateTransitionException(Exception):
    def __init__(self, from_state: AgentState, to_state: AgentState, agent_id: int, reason: str = ""):
        self.from_state = from_state
        self.to_state = to_state
        self.agent_id = agent_id
        self.reason = reason
        super().__init__(
            f"Invalid Agent transition for Agent #{agent_id}: {from_state.value} -> {to_state.value}. {reason}".strip()
        )

# Map of valid transitions
VALID_AGENT_TRANSITIONS = {
    AgentState.OFFLINE: {AgentState.AVAILABLE, AgentState.PAUSED},
    AgentState.AVAILABLE: {AgentState.RESERVED, AgentState.PAUSED, AgentState.OFFLINE, AgentState.CONNECTED},
    AgentState.RESERVED: {AgentState.DIALING, AgentState.AVAILABLE, AgentState.PAUSED, AgentState.OFFLINE},
    AgentState.DIALING: {AgentState.CONNECTED, AgentState.AVAILABLE, AgentState.WRAP_UP, AgentState.OFFLINE},
    AgentState.CONNECTED: {AgentState.WRAP_UP, AgentState.AVAILABLE, AgentState.OFFLINE},
    AgentState.WRAP_UP: {AgentState.AVAILABLE, AgentState.PAUSED, AgentState.OFFLINE},
    AgentState.PAUSED: {AgentState.AVAILABLE, AgentState.OFFLINE},
}

class AgentStateMachine:
    @staticmethod
    def can_transition(from_state: AgentState, to_state: AgentState) -> bool:
        if from_state == to_state:
            return True
        return to_state in VALID_AGENT_TRANSITIONS.get(from_state, set())

    @staticmethod
    def transition(agent, to_state: AgentState, reason: str = "") -> None:
        current_state = AgentState(agent.status)
        if current_state == to_state:
            return

        if not AgentStateMachine.can_transition(current_state, to_state):
            raise InvalidAgentStateTransitionException(current_state, to_state, agent.id, reason)

        now = datetime.now(timezone.utc)
        agent.status = to_state.value
        agent.last_status_change = now

        if to_state == AgentState.RESERVED:
            agent.reserved_at = now
        elif to_state == AgentState.CONNECTED:
            agent.connected_at = now
            agent.reserved_at = None
        elif to_state in {AgentState.AVAILABLE, AgentState.OFFLINE, AgentState.PAUSED}:
            agent.reserved_at = None
            agent.connected_at = None
            agent.current_call_id = None
