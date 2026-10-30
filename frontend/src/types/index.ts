export type AgentState = 
  | 'OFFLINE'
  | 'AVAILABLE'
  | 'RESERVED'
  | 'DIALING'
  | 'CONNECTED'
  | 'WRAP_UP'
  | 'PAUSED';

export type CallState = 
  | 'QUEUED'
  | 'RESERVED'
  | 'INITIATED'
  | 'RINGING'
  | 'ANSWERED'
  | 'CONNECTED'
  | 'COMPLETED'
  | 'FAILED'
  | 'CANCELLED';

export type DialingMode = 'PROGRESSIVE' | 'PREDICTIVE';

export type ProviderType = 'PROVIDER_A' | 'PROVIDER_B';

export type CircuitState = 'CLOSED' | 'OPEN' | 'HALF_OPEN';

export type SafetyDecisionType = 'APPROVED' | 'REDUCED' | 'REJECTED' | 'FALLBACK_PROGRESSIVE';

export interface Agent {
  id: number;
  name: string;
  status: AgentState;
  current_call_id: number | null;
  reserved_at: string | null;
  connected_at: string | null;
  last_status_change: string | null;
  version: number;
  total_calls_handled: number;
  total_talk_time_seconds: number;
}

export interface Call {
  id: number;
  idempotency_key: string;
  campaign_id: number;
  borrower_id: number;
  agent_id: number | null;
  provider_type: ProviderType;
  provider_call_id: string | null;
  status: CallState;
  created_at: string;
  initiated_at: string | null;
  ringing_at: string | null;
  answered_at: string | null;
  connected_at: string | null;
  completed_at: string | null;
  talk_duration_seconds: number;
  ring_duration_seconds: number;
  failure_reason: string | null;
  is_abandoned: boolean;
}

export interface SafetyDecisionAudit {
  id: number;
  campaign_id: number;
  timestamp: string;
  dialing_mode: string;
  requested_calls: number;
  approved_calls: number;
  decision_type: SafetyDecisionType;
  rationale: string;
  available_agents: number;
  ringing_calls: number;
  connected_calls: number;
  wrap_up_agents: number;
  answer_rate_used: number;
  expected_free_agents: number;
  provider_health_status: string;
}

export interface SystemMetrics {
  total_agents: number;
  available_agents: number;
  reserved_agents: number;
  dialing_agents: number;
  connected_agents: number;
  wrap_up_agents: number;
  paused_agents: number;
  offline_agents: number;
  agent_utilization_rate: number;

  queued_borrowers: number;
  in_flight_calls: number;
  ringing_calls: number;
  connected_calls: number;
  completed_calls: number;
  failed_calls: number;
  abandoned_calls: number;
  abandon_rate: number;

  current_dialing_mode: DialingMode;
  active_provider: ProviderType;
  provider_a_circuit: CircuitState;
  provider_b_circuit: CircuitState;
  estimated_answer_rate: number;
  last_safety_decision: SafetyDecisionAudit | null;
}
