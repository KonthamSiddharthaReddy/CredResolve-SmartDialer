# Failure Scenarios & Self-Healing Mechanisms

This document analyzes the 7 critical failure and edge-case scenarios required by CredResolve's assignment and details how the SmartDialer handles each.

---

## 1. Worker Crash After Reserving an Agent
### The Scenario
`Agent Reserved` $\longrightarrow$ `Borrower Reserved` $\longrightarrow$ **Worker Crashes** (Process Killed / Segmentation Fault / Power Loss).
### The Problem
The agent is left in `RESERVED` state and the borrower is left in `RESERVED` state. Without self-healing, both are leaked indefinitely, reducing operational capacity.
### How SmartDialer Solves It
1. **Heartbeat & Reservation TTL**: Every reservation stamps `reserved_at = datetime.now(timezone.utc)`. The reservation TTL is set to 10 seconds.
2. **Janitor Reaper (`RecoveryService.reap_stale_reservations`)**: A background recovery process scans for:
   ```sql
   SELECT id FROM agents WHERE status = 'RESERVED' AND reserved_at <= :cutoff;
   SELECT id FROM borrowers WHERE status = 'RESERVED' AND reserved_at <= :cutoff;
   ```
3. The Reaper atomically resets the agent to `AVAILABLE` (`reserved_at = NULL, version = version + 1`) and the borrower to `QUEUED`.
4. Verified by test: `test_stale_reservation_reaper_worker_crash`.

---

## 2. Worker Crash After Initiating a Call
### The Scenario
`Agent Reserved` $\longrightarrow$ `Call Initiated` with Provider $\longrightarrow$ **Worker Crashes before callback processed**.
### The Problem
The call is in `INITIATED` or `RINGING`, and the agent is in `DIALING`. The carrier might or might not have established the connection.
### How SmartDialer Solves It
1. **Call Timeout Reaper (`RecoveryService.reap_orphaned_calls`)**: Calls in `INITIATED` or `RINGING` have a strict SLA threshold (`CALL_INITIATION_TIMEOUT_SECONDS = 45s`).
2. If no carrier webhook or status update occurs within 45 seconds, the call is marked:
   `status = FAILED`, `failure_reason = 'ORPHANED_TIMEOUT_REAPER'`.
3. The allocated agent is released back to `AVAILABLE` (or `WRAP_UP`), and the borrower is returned to `QUEUED` with incremented `dial_attempts`.
4. Verified by test: `test_orphaned_call_reaper_worker_crash`.

---

## 3. Provider Outage & Timeouts
### The Scenario
The carrier starts timing out (HTTP 504 / Gateway Timeout / Connection Refused).
### What Happens To:
- **Existing Calls**: Calls already `CONNECTED` are on active audio channels and continue normally until hangup.
- **New Calls**:
  1. The Provider's internal **Circuit Breaker** tracks the rolling error rate over the last 20 requests.
  2. When the failure rate exceeds 40%, the circuit trips to `OPEN`.
  3. The **Safety Controller** detects `circuit_state == OPEN`.
  4. If in Predictive mode, it immediately **rejects speculative calls** or falls back to Progressive mode.
- **Retries**: Calls that failed due to gateway timeouts are rescheduled with exponential backoff on the borrower record; they are not endlessly retried in tight loops.
- **Pacing**: Pacing engine factors in `provider_failure_rate`, reducing raw call requests.

---

## 4. Agent Availability Suddenly Drops (100 $\rightarrow$ 60)
### The Scenario
100 agents are available, and 40 log off or go on break within seconds. Several calls are already in-flight/ringing.
### The Problem
If the predictive engine assumed 100 agents were available when placing 40 ringing calls, having only 60 agents might lead to an over-subscription spike when calls answer.
### How SmartDialer Solves It
1. **Instantaneous State Inspection**: Pacing and Safety checks do not use cached counts; they query the real-time database pool.
2. **Safety Rule 5 (Ringing vs Available Guard)**:
   ```python
   if ringing_calls >= available_agents and available_agents > 0:
       return SafetyEvaluation(decision_type=SafetyDecisionType.REJECTED, approved_calls=0)
   ```
3. New call initiation is **immediately halted** (0 approved calls) until in-flight ringing calls are resolved, preventing a surge of abandoned connected calls.

---

## 5. Duplicate Provider Events
### The Scenario
The carrier webhook sends: `ANSWERED` $\longrightarrow$ `ANSWERED` $\longrightarrow$ `ANSWERED` $\longrightarrow$ `COMPLETED`.
### The Problem
Naïve state handlers would attempt to bridge multiple agents or corrupt database counters.
### How SmartDialer Solves It
1. **Idempotent State Machine**:
   - When the first `ANSWERED` arrives: call moves `RINGING` $\rightarrow$ `ANSWERED` $\rightarrow$ `CONNECTED`.
   - When the second `ANSWERED` arrives: `CallStateMachine` detects `call.status == CONNECTED` and returns `is_duplicate = True`.
   - No additional agent reservation or counter modification is performed.
   - Handled with HTTP 200 acknowledgment to the carrier webhook.
2. Verified by test: `test_duplicate_answered_events_handling`.

---

## 6. Out-of-Order Events (COMPLETED before ANSWERED)
### The Scenario
Due to asynchronous network routing or UDP packet reordering, the carrier sends `COMPLETED` while the call is still marked `RINGING` or `INITIATED`. Later, a delayed `ANSWERED` arrives.
### How SmartDialer Solves It
1. **Out-of-Order Fast Forward**:
   `CallStateMachine` permits `INITIATED / RINGING` $\longrightarrow$ `COMPLETED`.
   The call duration is saved, and the call enters the terminal state `COMPLETED`.
   The assigned agent (if any) is released to `WRAP_UP`.
2. **Stale Event Discard**:
   When the delayed `ANSWERED` arrives later for the already `COMPLETED` call, the state machine flags it as `is_stale = True` and safely discards it without reopening the call.
3. Verified by test: `test_out_of_order_completed_before_answered`.

---

## 7. Provider Answer Rate Drops from 70% to 10%
### The Scenario
Carrier spam flagging (e.g. STIR/SHAKEN reputation drop or "Spam Likely" tagging) causes borrower answer rate to plummet from 70% to 10%.
### The Problem
If a predictive engine continues pacing at 70%, it will severely underdial. Conversely, if it suddenly ramps up dialing by $7\times$ based on high variance, an unexpected recovery burst would result in catastrophic call abandonments.
### How SmartDialer Solves It
1. **Exponential Moving Average (EMA)**: The dialer computes a rolling answer rate over the last 100 resolved calls.
2. **Safety Rule 4 (Crash Protection)**:
   ```python
   if current_answer_rate < 0.10:
       return SafetyEvaluation(
           decision_type=SafetyDecisionType.FALLBACK_PROGRESSIVE,
           is_fallback=True
       )
   ```
3. When the answer rate drops below 10%, speculative predictive dialing is disabled. The Safety Controller forces **Progressive 1:1 fallback**, maintaining zero abandoned calls until carrier reputation and answer rates stabilize.
