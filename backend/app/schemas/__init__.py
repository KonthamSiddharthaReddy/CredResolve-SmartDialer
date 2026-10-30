from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict
from backend.app.models.enums import AgentState, CallState, BorrowerStatus, DialingMode, ProviderType, SafetyDecisionType, CircuitState

class AgentBase(BaseModel):
    name: str

class AgentCreate(AgentBase):
    pass

class AgentResponse(AgentBase):
    id: int
    status: AgentState
    current_call_id: Optional[int] = None
    reserved_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    last_status_change: Optional[datetime] = None
    version: int
    total_calls_handled: int
    total_talk_time_seconds: float

    model_config = ConfigDict(from_attributes=True)

class AgentStateUpdateRequest(BaseModel):
    status: AgentState

class BorrowerResponse(BaseModel):
    id: int
    name: str
    phone: str
    status: BorrowerStatus
    priority: int
    campaign_id: Optional[int] = None
    dial_attempts: int

    model_config = ConfigDict(from_attributes=True)

class CampaignBase(BaseModel):
    name: str
    dialing_mode: DialingMode = DialingMode.PROGRESSIVE
    provider_type: ProviderType = ProviderType.PROVIDER_A
    target_abandon_rate: float = 0.01
    avg_talk_time_seconds: float = 90.0
    avg_ring_time_seconds: float = 20.0
    historical_answer_rate: float = 0.40

class CampaignCreate(CampaignBase):
    pass

class CampaignUpdate(BaseModel):
    dialing_mode: Optional[DialingMode] = None
    provider_type: Optional[ProviderType] = None
    is_active: Optional[bool] = None
    target_abandon_rate: Optional[float] = None
    avg_talk_time_seconds: Optional[float] = None
    avg_ring_time_seconds: Optional[float] = None
    historical_answer_rate: Optional[float] = None

class CampaignResponse(CampaignBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class CallResponse(BaseModel):
    id: int
    idempotency_key: str
    campaign_id: int
    borrower_id: int
    agent_id: Optional[int] = None
    provider_type: ProviderType
    provider_call_id: Optional[str] = None
    status: CallState
    created_at: datetime
    reserved_at: Optional[datetime] = None
    initiated_at: Optional[datetime] = None
    ringing_at: Optional[datetime] = None
    answered_at: Optional[datetime] = None
    connected_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    talk_duration_seconds: float
    ring_duration_seconds: float
    failure_reason: Optional[str] = None
    is_abandoned: bool

    model_config = ConfigDict(from_attributes=True)

class SafetyDecisionAuditResponse(BaseModel):
    id: int
    campaign_id: int
    timestamp: datetime
    dialing_mode: str
    requested_calls: int
    approved_calls: int
    decision_type: SafetyDecisionType
    rationale: str
    available_agents: int
    ringing_calls: int
    connected_calls: int
    wrap_up_agents: int
    answer_rate_used: float
    expected_free_agents: float
    provider_health_status: str

    model_config = ConfigDict(from_attributes=True)

class SystemMetricsResponse(BaseModel):
    total_agents: int
    available_agents: int
    reserved_agents: int
    dialing_agents: int
    connected_agents: int
    wrap_up_agents: int
    paused_agents: int
    offline_agents: int
    agent_utilization_rate: float  # (connected / (total - offline)) * 100

    queued_borrowers: int
    in_flight_calls: int
    ringing_calls: int
    connected_calls: int
    completed_calls: int
    failed_calls: int
    abandoned_calls: int
    abandon_rate: float            # (abandoned / (connected + abandoned)) * 100

    current_dialing_mode: DialingMode
    active_provider: ProviderType
    provider_a_circuit: CircuitState
    provider_b_circuit: CircuitState
    estimated_answer_rate: float
    last_safety_decision: Optional[SafetyDecisionAuditResponse] = None

class ProviderWebhookEvent(BaseModel):
    provider_call_id: str
    event_type: str  # INITIATED, RINGING, ANSWERED, COMPLETED, FAILED
    idempotency_key: Optional[str] = None
    timestamp: Optional[datetime] = None
    reason: Optional[str] = None
    talk_duration: Optional[float] = None

class FailureInjectionRequest(BaseModel):
    type: str  # "DROP_AGENTS", "RESTORE_AGENTS", "PROVIDER_OUTAGE", "RESTORE_PROVIDER", "ANSWER_RATE_CRASH", "WORKER_CRASH", "INJECT_DUPLICATE_WEBHOOK", "INJECT_OUT_OF_ORDER"
    params: Optional[Dict[str, Any]] = None
