# Engineering Notes & Technical Defense – CredResolve SmartDialer

**Candidate / Author Notes**  
**Project**: CredResolve SmartDialer (Progressive & Predictive Outbound Engine with Autonomous Safety Controller)  
**Target Role**: Backend / Full Stack Engineer  

---

## 1. Why I Selected This Technology Stack

When building this prototype, my goal was to satisfy every requirement of the hiring assignment while avoiding unnecessary operational bloat (e.g. premature Kubernetes clusters, Kafka brokers, or microservices that complicate running and reviewing a local prototype).

- **Python 3.12 + FastAPI**:
  - Outbound dialing involves concurrent I/O operations (carrier HTTP dispatch, webhook ingestion, database queries). FastAPI provides native async support (`asyncio`), high throughput, and automatic request/response schema validation via Pydantic v2.
  - Automatic OpenAPI / Swagger generation makes testing and inspecting endpoints transparent without needing Postman collections.

- **SQLite in Write-Ahead Logging (WAL) Mode**:
  - The assignment requested a local prototype using SQLite with proper transactional operations.
  - Default SQLite uses rollback journals, which lock the entire database on read and write. By configuring `PRAGMA journal_mode=WAL` and `PRAGMA busy_timeout=5000`, readers do not block writers and writers do not block readers.
  - *Engineering Trade-off*: SQLite still allows only **one writer at any given millisecond**. This is completely adequate for our prototype and test suite (~140 ops/sec), but in production, we migrate to PostgreSQL with `FOR UPDATE SKIP LOCKED`.

- **SQLAlchemy 2.0**:
  - Provides strict ORM model mapping and explicit transaction control (`session.commit()`, `session.rollback()`).
  - Allows us to execute atomic conditional SQL updates (`UPDATE ... WHERE id = :id AND version = :version`) rather than relying on in-memory object attributes.

- **React 18 + TypeScript + Vite + Tailwind CSS**:
  - The dashboard needs to visualize real-time agent states, call transitions, carrier latencies, and safety audit trails.
  - React with strict TypeScript typing prevents runtime schema mismatches between backend payloads and UI components.
  - Vite provides sub-second hot reloading during development and compact bundle outputs (`189 kB` JS gzip).

- **Pytest & Pytest-Asyncio**:
  - Selected for deterministic unit and concurrency test execution. Pytest fixtures enable isolated in-memory or temporary database instances for each test suite.

---

## 2. How the Complete System Works

The SmartDialer is organized into five decoupled layers where data flows in a single, predictable direction:

$$\text{Campaign Queue} \longrightarrow \text{Pacing Engine} \longrightarrow \mathbf{\text{Independent Safety Controller}} \longrightarrow \text{Call Allocator} \longrightarrow \text{Telecom Provider}$$

1. **Campaign Layer**: Holds the pool of collection agents, borrower call queues, and campaign operational targets (target abandonment rate $\le 1\%$, average talk time, historical answer rate).
2. **Pacing Layer**: Evaluates system state on every dialer tick and computes how many calls *could* be initiated based on the selected mode:
   - **Progressive Mode**: Strictly calculates $N = \max(0, A_{\text{avail}} - C_{\text{ring}})$.
   - **Predictive Mode**: Uses Little's Law and Poisson completion departure rates to forecast how many agents will become free during the carrier ringing window.
3. **Safety Controller Layer (The Regulatory Gatekeeper)**:
   - Sits directly between the pacing engine and the call allocator.
   - The predictive engine has **no capability** to place calls on its own.
   - The Safety Controller evaluates 6 independent invariant rules. It approves, reduces, rejects, or forces **1:1 Progressive Fallback** if any risk indicator trips.
4. **Call Allocator Layer**:
   - Takes approved call counts from the Safety Controller.
   - Atomically locks the borrower and (in progressive mode) the agent using database version checks.
   - Generates an idempotency key and dispatches the call to the carrier.
5. **Telecom Provider Layer**:
   - Interfaces with Provider A (fast, reliable) or Provider B (flaky, latency, timeouts, duplicate/out-of-order webhooks).
   - Each provider is protected by a 3-state Circuit Breaker (`CLOSED`, `OPEN`, `HALF_OPEN`).
   - Webhook callbacks (`RINGING`, `ANSWERED`, `COMPLETED`, `FAILED`) update the call state machine and release agents to `WRAP_UP`.

---

## 3. How Agent Allocation Works (Concurrency & State Safety)

### The Race Condition Problem
If Worker 1 and Worker 2 both query the database at the same time:
1. Both read `Agent #42` with `status = AVAILABLE`.
2. Worker 1 assigns Agent #42 to Borrower A.
3. Worker 2 assigns Agent #42 to Borrower B.
4. Two calls dial out; both borrowers answer, but only one agent exists. The second call is **abandoned**—violating compliance.

### How We Solve It in the Prototype
We do not use in-memory locks (like Python `threading.Lock()`), because in-memory locks do not protect across multiple worker processes, multi-core Uvicorn instances, or distributed containers.

Instead, we use **Optimistic Concurrency Control (OCC) with atomic conditional database updates**:
```python
stmt = (
    update(Agent)
    .where(
        Agent.id == agent_id,
        Agent.status == AgentState.AVAILABLE.value,
        Agent.version == current_version
    )
    .values(
        status=AgentState.RESERVED.value,
        reserved_at=now,
        last_status_change=now,
        version=Agent.version + 1
    )
)
result = db.execute(stmt)
db.commit()
return result.rowcount > 0
```

### What Happens Step-by-Step:
1. Worker 1 and Worker 2 both observe Agent #42 with `version = 1`.
2. Both execute the atomic update.
3. SQLite WAL serializes the write commit. Worker 1's query executes first:
   - `Agent #42` status becomes `RESERVED`, and `version` increments to `2`.
   - `result.rowcount` is `1` (Success).
4. Worker 2's query executes immediately after:
   - Because `status` is no longer `AVAILABLE` and `version` is no longer `1`, the `WHERE` clause matches 0 rows.
   - `result.rowcount` is `0` (Conflict detected).
5. Worker 2 catches the `rowcount == 0`, rolls back, and automatically advances to the next candidate agent in the queue.
6. **Result**: Zero double-allocations, zero in-memory bottlenecks. Verified by `test_concurrency.py` and benchmark load scripts.

---

## 4. How the Safety Controller Protects Borrowers

In debt collection, an **abandoned call** occurs when a borrower answers the phone and no human agent is bridged within 2 seconds. In India (RBI), the US (FTC/FCC), and the UK (Ofcom), abandonment rates above 1% to 3% carry severe financial and legal penalties.

The Safety Controller acts as an unbypassable circuit-breaker and compliance governor. It evaluates 6 orthogonal rules on every dial tick:

1. **Rule 1: Zero Agent Guard**:
   If there are 0 available agents, 0 wrap-up agents, and 0 connected calls, all call requests are immediately rejected (`approved = 0`).
2. **Rule 2: Carrier Circuit Breaker Guard**:
   If the telecom provider circuit is `OPEN` (carrier outage), calls are rejected. If `HALF_OPEN` (canary testing), only 1 progressive probe call is allowed. If carrier failure rate $\ge 30\%$, predictive mode is forced to Progressive.
3. **Rule 3: Compliance Abandonment Tripwire**:
   If even **a single call** was abandoned in the recent sample window, or if the rolling abandonment rate exceeds $1\%$, speculative predictive dialing is disabled immediately. The system forces **1:1 Progressive Fallback**.
4. **Rule 4: Answer Rate Collapse Protection**:
   If carrier spam flagging causes the answer rate to collapse below $10\%$, a predictive model might blindly try to dial $10\times$ more calls to compensate. The Safety Controller detects this collapse and forces **Progressive Fallback** to avoid flooding the carrier.
5. **Rule 5: Ringing vs. Available Capacity Guard**:
   If the number of currently ringing calls already equals or exceeds available agents ($C_{\text{ring}} \ge A_{\text{avail}}$), no additional speculative calls are approved unless there is high connected call turnover.
6. **Rule 6: Binomial Upper Confidence Limit (UCL) Ceiling**:
   Replaces arbitrary static multipliers with a mathematically defensible statistical ceiling (detailed below).

---

## 5. How Predictive Pacing is Calculated

The predictive engine aims to maximize agent utilization without causing abandoned calls. It operates on **Little's Law** and **Poisson completion departure rates**.

### Step 1: Effective Timing Windows
$$\text{Ring Window} = \max(5.0, T_{\text{ring}} + L_{\text{provider}})$$
$$\text{Talk Time} = \max(10.0, T_{\text{talk}})$$
Where $L_{\text{provider}}$ is carrier network latency.

### Step 2: Expected Agents Freeing Up
Under Poisson call completions ($\lambda = \frac{C_{\text{conn}}}{T_{\text{talk}}}$), the expected number of agents who will finish their current call while the new outbound call is still ringing is:
$$E[\text{freeing}] = C_{\text{conn}} \times \left(\frac{\text{Ring Window}}{\text{Talk Time}}\right) + (A_{\text{wrap}} \times 0.8)$$
*(Wrap-up agents are weighted at 80% likelihood of finishing within the ring window).*

### Step 3: Projected Agent Capacity
$$\text{Projected Capacity } (C_{\text{proj}}) = A_{\text{avail}} + E[\text{freeing}]$$

### Step 4: Existing Ringing In-Flight Discount
Calls that were initiated in earlier seconds and are already ringing have an expected answer yield:
$$E[\text{answers}_{\text{in-flight}}] = C_{\text{ring}} \times p_{\text{eff}}$$
Where $p_{\text{eff}} = p_{\text{hist}} \times (1 - \text{failure\_rate}_{\text{provider}})$.

### Step 5: Unfilled Capacity & Raw Calls
$$\text{Unfilled Capacity } (C_{\text{unfilled}}) = \max(0, C_{\text{proj}} - E[\text{answers}_{\text{in-flight}}])$$
$$\text{Raw Calls Needed} = \frac{C_{\text{unfilled}}}{p_{\text{eff}}}$$

### Step 6: Variance Damping & Engine Sanity Cap
To guard against random answer clustering, a 90% confidence discount factor ($0.90$) is applied:
$$\text{Damped Calls} = \text{Raw Calls} \times 0.90$$

### Step 7: Binomial Upper Confidence Limit (UCL) Safety Ceiling
Static multipliers (like an arbitrary $3.0\times$) are flawed: at $70\%$ answer rates, $3\times$ dials produces $2.1\times$ answers (guaranteed abandonment); at $15\%$ answer rates, $3\times$ produces only $0.45\times$ answers (under-utilization).

Instead, the Safety Controller solves for the maximum dials $N$ such that:
$$P(\text{Live Answers} > C_{\text{proj}}) \le \alpha \quad (\alpha = 0.01)$$
Using the inverted Normal approximation to the Binomial distribution $B(N, p)$:
$$C_{\text{proj}} \ge N p + z_{1-\alpha} \sqrt{N p (1 - p)}$$
Solving the quadratic in $u = \sqrt{N}$ ($z_{0.99} = 2.3263$):
$$u = \frac{-z \sqrt{p(1-p)} + \sqrt{z^2 p(1-p) + 4 p C_{\text{proj}}}}{2p}$$
$$N_{\text{safe}} = \max\left(A_{\text{avail}}, \lfloor u^2 \rfloor\right)$$
The final approved quantity is clamped to $\min(\text{Damped Calls}, N_{\text{safe}} - C_{\text{ring}})$.

---

## 6. How Duplicate and Out-of-Order Events are Handled

Telecom carrier webhooks are notoriously asynchronous and unreliable:

1. **Duplicate Webhook (`ANSWERED` $\rightarrow$ `ANSWERED`)**:
   - When the first `ANSWERED` event arrives, the call moves `RINGING` $\rightarrow$ `ANSWERED` $\rightarrow$ `CONNECTED`.
   - When the second `ANSWERED` event arrives, `CallStateMachine.transition()` detects `current_state == CONNECTED`.
   - The state machine immediately returns `CallTransitionResult(success=True, is_duplicate=True)`.
   - The webhook handler returns HTTP 200 without attempting another agent reservation or modifying counters.
2. **Out-of-Order Webhook (`COMPLETED` before `ANSWERED`)**:
   - Provider B occasionally delivers `COMPLETED` while the call is still marked `RINGING`.
   - The state machine allows `RINGING` $\rightarrow$ `COMPLETED`, sets `is_out_of_order = True`, records talk duration, and releases any held agent to `WRAP_UP`.
   - If the delayed `ANSWERED` event arrives seconds later, the state machine recognizes that `COMPLETED` is a terminal state, flags `is_stale = True`, and safely discards it.
3. **Idempotency Keys**:
   - Every call dispatch generates a unique compound idempotency key:
     `camp-{campaign_id}-b-{borrower_id}-ts-{timestamp_ms}-{uuid_hex}`
   - Retrying a call with the same idempotency key is rejected by database unique constraints.

---

## 7. How Concurrent Workers are Managed

1. **Shared Database as Source of Truth**:
   - We do not coordinate workers using distributed locks (e.g. Redlock), which can fail during network partitions.
   - The database transaction boundary is the single source of truth.
2. **Database Busy Timeout & WAL Mode**:
   - In SQLite, concurrent writes acquire a short-lived table write lock. By configuring `PRAGMA busy_timeout = 5000`, worker threads wait up to 5 seconds for transient locks to clear rather than failing immediately with `sqlite3.OperationalError: database is locked`.
3. **Graceful Skip on Contention**:
   - Worker queries fetch candidate rows ordered by `last_status_change ASC` with a `LIMIT 10` window.
   - If Worker 1 claims Candidate 0, Worker 2's conditional update on Candidate 0 fails cleanly (`rowcount == 0`), and Worker 2 immediately reserves Candidate 1.

---

## 8. What Happens During a Worker Crash

We analyze and handle crashes at all three critical lifecycle moments:

### Case A: Worker crashes after reserving an agent/borrower (before carrier dispatch)
- **State**: Agent is `RESERVED`, Borrower is `RESERVED`, Call is `RESERVED`.
- **Handling**: Every reservation records `reserved_at = datetime.now(timezone.utc)`.
- The background **Janitor Reaper** (`RecoveryService.reap_stale_reservations`) runs on every dialer tick and sweeps any reservation where:
  $$\text{now} - \text{reserved\_at} > \text{RESERVATION\_TTL\_SECONDS } (10\text{s})$$
- The agent is returned to `AVAILABLE`, the borrower is returned to `QUEUED`, and the aborted call is marked `FAILED (WORKER_CRASH_BEFORE_DISPATCH)`.

### Case B: Worker crashes after dispatching call to carrier
- **State**: Call is `INITIATED` or `RINGING`, Agent is `DIALING`.
- **Handling**: If the worker died and the carrier callback never arrives (or carrier dropped the connection), the **Orphaned Call Reaper** sweeps calls where:
  $$\text{now} - \text{created\_at} > \text{CALL\_INITIATION\_TIMEOUT\_SECONDS } (45\text{s})$$
- The call is marked `FAILED (ORPHANED_TIMEOUT_REAPER)`, the agent is returned to `AVAILABLE`, and the borrower is requeued.

### Case C: Webhook arrives after worker restarted
- Because call and agent states are stored in the database (not in worker memory), any running worker instance can receive and process the webhook using the call's `provider_call_id`.

---

## 9. What I Would Improve With Another Week

If I had another week to take this prototype into enterprise production, I would prioritize:

1. **PostgreSQL Migration with `FOR UPDATE SKIP LOCKED`**:
   - Replace SQLite optimistic versioning with PostgreSQL row-level locking. This eliminates OCC retry loops under heavy concurrency and supports hundreds of parallel worker pods.
2. **Redis In-Memory Token Bucket for Carrier CPS Limits**:
   - Telecom carriers strictly limit Calls Per Second (e.g. 30 CPS per SIP trunk). I would implement a Redis token bucket to smooth out bursty dialing spikes across distributed workers.
3. **WebSockets / Server-Sent Events (SSE) for Dashboard**:
   - Replace the current 1.5-second HTTP polling in the React dashboard with SSE or WebSocket channels pushed directly from FastAPI background events.
4. **Kalman Filter or Dynamic Bayesian Updating for Answer Rates**:
   - The current EMA (Exponential Moving Average) adapts to answer rate changes over a trailing 100-call window. A Bayesian model incorporating time-of-day, borrower risk tier, and carrier reputation would adapt faster to sudden shifts.
5. **Decoupled Asynchronous Worker Queue (Celery / ARQ / Redis Streams)**:
   - Move carrier network calls entirely out of the HTTP cycle into dedicated background worker queues with per-task retry policies and dead-letter queues (DLQs).

---

## 10. Architectural Decisions I am Prepared to Defend in an Interview

| Decision | Why I Made It | What I'd Say to a Reviewer |
|---|---|---|
| **Independent Safety Controller as a separate class** | Decouples compliance from optimization. The predictive engine cannot be trusted with legal limits. | *"Pacing math optimizes for throughput, but safety optimizes for regulatory compliance. By making the Safety Controller an unbypassable gatekeeper, we ensure that an optimization bug can never create a regulatory violation."* |
| **Binomial UCL Ceiling vs. 3.0x Multiplier** | A static $3\times$ multiplier is statistically indefensible at high or low answer rates. | *"At 70% answer rate, dialing 3x capacity guarantees 2.1x live answers—causing mass abandonments. The Binomial UCL ceiling mathematically bounds $P(\text{Answers} > \text{Capacity}) \le 1\%$ regardless of whether answer rates are 10% or 80%."* |
| **SQLite WAL Mode for Prototype** | Zero-dependency evaluation without running local Postgres containers. | *"For a local prototype and recruitment review, SQLite with WAL mode and busy timeouts delivers ~144 atomic operations per second with zero setup friction. In production, we swap the SQLAlchemy connection string to PostgreSQL and use `FOR UPDATE SKIP LOCKED`."* |
| **Optimistic Versioning vs. In-Memory Mutexes** | In-memory locks fail across multiple processes or containers. | *"Database-level atomic conditional updates (`WHERE version = :version`) guarantee race condition safety across any number of worker processes without shared memory dependencies."* |
| **Dynamic Agent Rescue on Webhook** | An agent reserved during progressive dialing might pause or crash while the phone is ringing. | *"If an assigned agent becomes unavailable while the phone is ringing, our webhook handler attempts a dynamic rescue with another free agent. Only if no agents exist in the entire pool does it mark the call abandoned."* |

---

*These notes reflect the actual implementation and codebase located in `d:\cred`.*
