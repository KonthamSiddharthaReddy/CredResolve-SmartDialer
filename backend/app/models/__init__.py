from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from backend.app.database import Base
from backend.app.models.enums import AgentState, CallState, BorrowerStatus, DialingMode, ProviderType, SafetyDecisionType, CircuitState

def utcnow():
    return datetime.now(timezone.utc)

class Agent(Base):
    __tablename__ = "agents"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    status = Column(String(50), nullable=False, default=AgentState.OFFLINE.value, index=True)
    current_call_id = Column(Integer, nullable=True)
    reserved_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)
    last_status_change = Column(DateTime, default=utcnow, onupdate=utcnow)
    version = Column(Integer, default=1, nullable=False)  # Optimistic concurrency version
    total_calls_handled = Column(Integer, default=0)
    total_talk_time_seconds = Column(Float, default=0.0)

class Borrower(Base):
    __tablename__ = "borrowers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    phone = Column(String(30), nullable=False, index=True)
    status = Column(String(50), nullable=False, default=BorrowerStatus.QUEUED.value, index=True)
    priority = Column(Integer, default=1)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=True)
    reserved_at = Column(DateTime, nullable=True)
    version = Column(Integer, default=1, nullable=False)  # Optimistic concurrency version
    dial_attempts = Column(Integer, default=0)
    last_attempt_at = Column(DateTime, nullable=True)

class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    dialing_mode = Column(String(50), nullable=False, default=DialingMode.PROGRESSIVE.value)
    provider_type = Column(String(50), nullable=False, default=ProviderType.PROVIDER_A.value)
    is_active = Column(Boolean, default=True)
    target_abandon_rate = Column(Float, default=0.01)
    avg_talk_time_seconds = Column(Float, default=90.0)
    avg_ring_time_seconds = Column(Float, default=20.0)
    historical_answer_rate = Column(Float, default=0.40)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow, onupdate=utcnow)

class Call(Base):
    __tablename__ = "calls"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(100), unique=True, index=True, nullable=False)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False, index=True)
    borrower_id = Column(Integer, ForeignKey("borrowers.id"), nullable=False, index=True)
    agent_id = Column(Integer, ForeignKey("agents.id"), nullable=True, index=True)
    provider_type = Column(String(50), nullable=False)
    provider_call_id = Column(String(100), nullable=True, index=True)
    status = Column(String(50), nullable=False, default=CallState.QUEUED.value, index=True)
    created_at = Column(DateTime, default=utcnow)
    reserved_at = Column(DateTime, nullable=True)
    initiated_at = Column(DateTime, nullable=True)
    ringing_at = Column(DateTime, nullable=True)
    answered_at = Column(DateTime, nullable=True)
    connected_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    talk_duration_seconds = Column(Float, default=0.0)
    ring_duration_seconds = Column(Float, default=0.0)
    failure_reason = Column(String(200), nullable=True)
    is_abandoned = Column(Boolean, default=False)
    version = Column(Integer, default=1, nullable=False)

class SafetyDecisionAudit(Base):
    __tablename__ = "safety_decision_audits"

    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow, index=True)
    dialing_mode = Column(String(50), nullable=False)
    requested_calls = Column(Integer, nullable=False)
    approved_calls = Column(Integer, nullable=False)
    decision_type = Column(String(50), nullable=False)
    rationale = Column(String(500), nullable=False)
    available_agents = Column(Integer, default=0)
    ringing_calls = Column(Integer, default=0)
    connected_calls = Column(Integer, default=0)
    wrap_up_agents = Column(Integer, default=0)
    answer_rate_used = Column(Float, default=0.0)
    expected_free_agents = Column(Float, default=0.0)
    provider_health_status = Column(String(50), default="HEALTHY")

class ProviderAuditLog(Base):
    __tablename__ = "provider_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    provider_name = Column(String(50), nullable=False, index=True)
    timestamp = Column(DateTime, default=utcnow)
    event_type = Column(String(50), nullable=False)
    call_id = Column(Integer, nullable=True)
    provider_call_id = Column(String(100), nullable=True)
    idempotency_key = Column(String(100), nullable=True)
    latency_ms = Column(Float, default=0.0)
    is_duplicate = Column(Boolean, default=False)
    is_out_of_order = Column(Boolean, default=False)
    details = Column(String(500), nullable=True)
