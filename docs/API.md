# CredResolve SmartDialer REST API Documentation

Base URL: `http://localhost:8000/api/v1`

---

## 1. Dialer & Telemetry Endpoints

### `POST /dialer/cycle`
Runs a single dialing cycle for the specified campaign.
- **Query Params**: `campaign_id` (integer, default: 1)
- **Response**:
```json
{
  "status": "success",
  "campaign_id": 1,
  "mode": "PREDICTIVE",
  "safety_decision": "APPROVED",
  "safety_rationale": "Safety approved: 12 call(s) safely within regulatory risk parameters.",
  "approved_calls": 12,
  "initiated_calls_count": 12,
  "initiated_call_ids": [101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111, 112]
}
```

### `GET /dialer/metrics`
Returns rich real-time operational metrics for dashboard visualization.
- **Query Params**: `campaign_id` (integer, default: 1)
- **Response**:
```json
{
  "total_agents": 50,
  "available_agents": 22,
  "reserved_agents": 0,
  "dialing_agents": 8,
  "connected_agents": 18,
  "wrap_up_agents": 2,
  "paused_agents": 0,
  "offline_agents": 0,
  "agent_utilization_rate": 36.0,
  "queued_borrowers": 142,
  "in_flight_calls": 8,
  "ringing_calls": 8,
  "connected_calls": 18,
  "completed_calls": 32,
  "failed_calls": 4,
  "abandoned_calls": 0,
  "abandon_rate": 0.0,
  "current_dialing_mode": "PREDICTIVE",
  "active_provider": "PROVIDER_A",
  "provider_a_circuit": "CLOSED",
  "provider_b_circuit": "CLOSED",
  "estimated_answer_rate": 0.48,
  "last_safety_decision": {
    "id": 45,
    "campaign_id": 1,
    "timestamp": "2026-10-30T12:00:00Z",
    "dialing_mode": "PREDICTIVE",
    "requested_calls": 12,
    "approved_calls": 12,
    "decision_type": "APPROVED",
    "rationale": "Predictive model: 22 available agents + 3.6 expected completions...",
    "available_agents": 22,
    "ringing_calls": 8,
    "connected_calls": 18,
    "wrap_up_agents": 2,
    "answer_rate_used": 0.48,
    "expected_free_agents": 3.6,
    "provider_health_status": "CLOSED"
  }
}
```

### `GET /dialer/safety-audits`
Fetches historical Safety Controller decisions.
- **Query Params**: `campaign_id` (int), `limit` (int, default: 20)

---

## 2. Campaign Management

### `GET /campaigns`
Lists all campaigns.

### `PATCH /campaigns/{campaign_id}`
Updates campaign parameters.
- **Request Body**:
```json
{
  "dialing_mode": "PROGRESSIVE",
  "provider_type": "PROVIDER_B",
  "is_active": true,
  "avg_talk_time_seconds": 90.0,
  "historical_answer_rate": 0.50
}
```

---

## 3. Agents & Calls

### `GET /agents`
- **Query Params**: `status` (optional: `AVAILABLE`, `CONNECTED`, etc.), `limit` (default: 100)

### `PATCH /agents/{agent_id}/status`
Manually updates an agent's state with state machine validation.
- **Request Body**: `{"status": "PAUSED"}`

### `GET /calls/active`
Returns currently active calls (`INITIATED`, `RINGING`, `ANSWERED`, `CONNECTED`).

---

## 4. Telecom Webhooks (Idempotent Carrier Callbacks)

### `POST /webhooks/provider`
Idempotent webhook endpoint for carrier status updates.
- **Request Body**:
```json
{
  "provider_call_id": "PA-101-abcd1234",
  "event_type": "ANSWERED",
  "idempotency_key": "camp-1-b-5-ts-1730000000",
  "talk_duration": 45.2
}
```
- **Responses**:
  - `status`: `"processed"`
  - `status`: `"duplicate"`, `is_duplicate: true` (if identical event already processed)
  - `status`: `"stale"`, `is_stale: true` (if delayed event arrives for completed call)

---

## 5. Simulation & Chaos Injection

### `POST /simulation/scenario`
Sets active scenario: `SCENARIO_A`, `SCENARIO_B`, `SCENARIO_C`, or `SCENARIO_D`.

### `POST /simulation/tick`
Steps the simulation engine forward by $N$ ticks.

### `POST /simulation/failure`
Injects chaos / failure condition:
- `DROP_AGENTS`: `{"type": "DROP_AGENTS", "params": {"count": 40}}`
- `RESTORE_AGENTS`: `{"type": "RESTORE_AGENTS"}`
- `PROVIDER_OUTAGE`: `{"type": "PROVIDER_OUTAGE"}`
- `RESTORE_PROVIDER`: `{"type": "RESTORE_PROVIDER"}`
- `ANSWER_RATE_CRASH`: `{"type": "ANSWER_RATE_CRASH", "params": {"rate": 0.10}}`
- `WORKER_CRASH`: `{"type": "WORKER_CRASH"}`
- `INJECT_DUPLICATE_WEBHOOK`: `{"type": "INJECT_DUPLICATE_WEBHOOK"}`
- `INJECT_OUT_OF_ORDER`: `{"type": "INJECT_OUT_OF_ORDER"}`

### `POST /simulation/recover`
Manually triggers the Janitor Reaper to reclaim stale reservations and orphaned calls.

### `POST /simulation/reset`
Resets the simulation database, seeding fresh agents, queued borrowers, and default campaign.
