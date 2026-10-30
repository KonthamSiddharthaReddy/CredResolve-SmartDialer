# CredResolve SmartDialer

> **High-Throughput Progressive & Predictive Outbound Dialer with an Autonomous Independent Safety Controller for Compliant Collections.**

Built for the **CredResolve Backend / Full Stack Engineer Hiring Assignment (2026)**.

---

## 1. Executive Summary

In debt collection operations, agents spend significant time waiting for outbound calls to connect.
- **Progressive Dialing** (1 available agent $\rightarrow$ 1 outbound call) is deterministic and safe, but leaves agents idle.
- **Predictive Dialing** initiates calls speculatively before agents become free based on estimated answer rates, but risks **abandoned connected calls** (borrower answers with no agent available)—a severe compliance violation.

**CredResolve SmartDialer** bridges this divide:
1. **Both Dialing Modes**: Supports deterministic **Progressive (1:1)** and statistical **Predictive** dialing (modeled with Little's Law, Poisson completion departures, and variance damping).
2. **Autonomous Independent Safety Controller**: The predictive algorithm **never** directly initiates calls. An unbypassable Safety Controller sits between the pacing engine and telecom providers, approving, reducing, rejecting, or forcing progressive fallback.
3. **Distributed-System Safety**: Atomic agent & borrower reservations, optimistic concurrency control with version increments, unique idempotency keys, and automated Janitor Reapers that self-heal after worker crashes.
4. **Mock Telecom Providers & Circuit Breakers**:
   - **Provider A**: Fast (~80ms), reliable (>98% success).
   - **Provider B**: High latency, timeouts, duplicate events, and out-of-order events.
   - Built-in **3-State Circuit Breakers** (`CLOSED`, `OPEN`, `HALF_OPEN`).
5. **Interactive Fintech Dashboard**: High-density React + TypeScript interface visualizing agent states, real-time pacing math, active calls, scenario controls (A, B, C, D), and live chaos injection.
6. **100% Automated Test Coverage**: 31 unit, concurrency, pacing, safety, and recovery tests passing via `pytest`.

---

## 2. Core Architecture Pipeline

```mermaid
flowchart LR
    Campaign[Campaign Queue] --> Pacing[Pacing Engine\n(Progressive / Predictive)]
    Pacing -->|Desired Calls| Safety[Independent Safety Controller\n(Regulatory Guard & Circuit Breaker)]
    Safety -->|Approved Calls| Allocator[Call Allocator\n(Atomic Locks & Idempotency)]
    Allocator --> Provider[Telecom Provider\n(Provider A / Provider B)]
```

> [!IMPORTANT]
> The predictive engine **cannot** bypass or disable the Safety Controller. If an abandoned call occurs, if carrier latency spikes, or if answer rates crash, the Safety Controller automatically overrides predictive requests and enforces 1:1 Progressive Mode.

---

## 3. Technology Stack

- **Backend**: Python 3.12 + FastAPI (Async REST APIs)
- **Database**: SQLite with Write-Ahead Logging (`WAL` mode) and busy timeout
- **ORM & Concurrency**: SQLAlchemy 2.0 with optimistic versioning (`version = version + 1`)
- **Frontend**: React 18 + TypeScript + Vite + Tailwind CSS (Fintech design)
- **Telecom Simulation**: Custom event-driven mock providers with circuit breakers
- **Testing**: `pytest` + `pytest-asyncio` (31 tests covering all edge cases)
- **Containerization**: Docker & Docker Compose multi-stage build

---

## 4. Quickstart: Running Locally

### Prerequisites
- Python 3.12+ (or [uv](https://docs.astral.sh/uv/))
- Node.js 18+ & npm

### Option A: Running with `uv` (Fastest)

```bash
# 1. Clone repository
git clone <repo-url>
cd credresolve-smartdialer

# 2. Run backend (automatically creates DB & seeds agents/borrowers)
uv run python backend/run_server.py
```
Backend API and documentation will be available at:
- **API Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

```bash
# 3. In a separate terminal, start frontend dashboard
cd frontend
npm install
npm run dev
```
Frontend Dashboard will open at: **[http://localhost:3000](http://localhost:3000)** (proxies API calls to port 8000).

---

### Option B: Running with Standard Python & Virtualenv

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install backend dependencies
pip install -r backend/requirements.txt

# Start backend server
python backend/run_server.py
```

---

### Option C: Running with Docker Compose

```bash
docker-compose up --build
```
Access the application at [http://localhost:8000](http://localhost:8000).

---

## 5. Running Automated Tests

Run the complete test suite with `pytest`:

```bash
uv run pytest -v
```

### Test Suite Coverage (31 Tests Passing):
- **Agent & Call State Machines**: Strict state transitions, duplicate event idempotency, out-of-order event recovery.
- **Progressive Dialing**: Zero overdial guarantees ($A_{avail} \ge C_{out}$).
- **Predictive Pacing Engine**: Little's Law formula, freeing agent departure rates, statistical damping.
- **Independent Safety Controller**: Boundary enforcement, clamping overdialing, progressive fallback on abandoned calls or circuit breaker trips.
- **Distributed Concurrency**: Multi-threaded worker race conditions on agent reservations and borrower queues (atomic conditional updates).
- **Mock Telecom Providers**: Latency simulation, timeouts, duplicate webhooks, out-of-order webhooks.
- **Crash Recovery & Reaper**: Stale reservation TTL sweeper, orphaned in-flight call timeout recovery.
- **Circuit Breaker**: CLOSED $\rightarrow$ OPEN $\rightarrow$ HALF-OPEN $\rightarrow$ CLOSED lifecycle.
- **Simulation Scenarios**: Scenarios A, B, C, D simulation runs and zero-abandonment verification.

---

## 6. Simulation & Failure Injection Scenarios

The frontend dashboard includes an interactive **Chaos & Failure Simulation Suite** testing all scenarios from the assignment:

| Scenario / Failure Condition | System Response & Self-Healing |
|---|---|
| **Scenario A** (20% Ans, 120s Talk) | Conservative predictive pacing; hedges against long talk times. |
| **Scenario B** (50% Ans, 90s Talk) | Balanced high-throughput pacing; maintains ~75% agent utilization. |
| **Scenario C** (70% Ans, 180s Talk) | High answer pacing; aggressively fills freed agent slots. |
| **Scenario D** (Dynamic Fluctuations) | Waveform modulation of answer rate & carrier latency; tests dynamic pacing adjustments. |
| **Drop 40 Agents (100 $\rightarrow$ 60)** | Safety Controller detects ringing calls $\ge$ available agents and **halts new dialing** until in-flight calls clear. |
| **Provider Outage / Timeouts** | Provider Circuit Breaker trips to `OPEN`; Safety Controller forces progressive mode or rejects calls. |
| **Answer Rate Crash (70% $\rightarrow$ 10%)** | Safety Controller detects collapse below 10% threshold and forces **Progressive Fallback**. |
| **Worker Crash** | Janitor Reaper detects stale reservations older than 10s TTL and restores agents to `AVAILABLE` and borrowers to `QUEUED`. |
| **Duplicate Webhook (`ANSWERED`)** | Call state machine recognizes duplicate event idempotently; returns HTTP 200 without double-allocation. |
| **Out-of-Order Webhook (`COMPLETED` before `ANSWERED`)** | State machine moves directly to `COMPLETED`; trailing delayed `ANSWERED` is discarded as stale. |

---

## 7. Technical Interview Q&A (From Assignment PDF)

### Q1: Two workers try to reserve the same agent at exactly the same time. Walk us through what happens.
**Answer:** Both workers query the database and may find Agent #42 in state `AVAILABLE` with `version = 1`.
Each worker executes an atomic conditional update:
```sql
UPDATE agents 
SET status = 'RESERVED', reserved_at = :now, version = version + 1 
WHERE id = 42 AND status = 'AVAILABLE' AND version = 1;
```
SQLite WAL mode serializes the transaction write lock.
- **Worker 1** commits first: SQLite updates 1 row (`rowcount == 1`). Agent #42 is now `RESERVED` with `version = 2`.
- **Worker 2** executes immediately after: because status is no longer `AVAILABLE` and version is no longer `1`, the WHERE clause matches 0 rows (`rowcount == 0`).
- Worker 2 detects the conflict, automatically skips Agent #42, and attempts reservation on the next candidate in the queue. Zero double-allocations occur.

---

### Q2: Your database says the agent is AVAILABLE, but your cache says RESERVED. Which one wins?
**Answer:** The **Database is always the single source of truth (SSOT)** for transactional state.
- In distributed architecture, caches (e.g. Redis) are volatile and vulnerable to network partitions or async replication lag.
- The cache serves only as a hint for fast lookup. The worker **must always** perform an atomic conditional check against the database before proceeding.
- If cache says `RESERVED` but DB says `AVAILABLE`, the worker verifies the reservation TTL. If the TTL expired, the cache key is purged and the database state wins.

---

### Q3: The provider sends ANSWERED, your worker crashes, and then COMPLETED arrives. What happens?
**Answer:**
1. The call was transitioned to `ANSWERED`.
2. The worker crashed before bridging the agent or updating subsequent records.
3. When `COMPLETED` arrives at the webhook handler:
   The call state machine detects that `COMPLETED` is a valid terminal transition from `ANSWERED`. It updates `call.status = COMPLETED`, records talk duration, and releases any associated agent to `WRAP_UP`.
4. If `COMPLETED` had never arrived, the background **Orphaned Call Reaper** would have caught the call after `CALL_INITIATION_TIMEOUT_SECONDS` (45s), marking it `FAILED (ORPHANED_TIMEOUT)` and freeing the agent.

---

### Q4: Your model predicted a 70% answer rate. It suddenly drops to 10%. How does the system protect itself?
**Answer:**
1. The system tracks answer rates using an Exponential Moving Average (EMA) over the last 100 resolved calls.
2. The **Safety Controller** enforces Rule 4:
   If `current_answer_rate < 0.10`, speculative dialing is prohibited.
3. The Safety Controller immediately trips into **FALLBACK_PROGRESSIVE** mode, restricting new calls to a strict 1:1 mapping with available agents until the answer rate recovers above threshold.

---

### Q5: We just went from 1,000 to 100,000 agents. What breaks first?
**Answer:**
1. **Centralized Database Write IOPS**: At 100,000 agents, call event throughput exceeds 15,000 events/second. A single primary SQL database suffers extreme write lock contention and replication lag.
   *Fix*: Partition by **Cell-Based Architecture** (sharding into autonomous 1,000-agent clusters with independent queues, safety controllers, and DB instances).
2. **Database Row Lock Contention on Agent Allocation**:
   *Fix*: Migrate from optimistic versioning to PostgreSQL `FOR UPDATE SKIP LOCKED`, or allocate via Redis in-memory atomic sets (`SPOP`).
3. **Carrier SIP Trunk Capacity & Audio Latency**: Real-time RTP audio streams cannot be routed through a central server without degrading latency ($>150\text{ms}$).
   *Fix*: Deploy geographically distributed Session Border Controllers (FreeSWITCH/Kamailio) to terminate audio locally.

---

### Q6: Why did your algorithm decide to initiate 17 calls instead of 10?
**Answer:**
The Predictive Engine's decision rationale is fully explainable:
1. Current available agents = $5$.
2. Currently connected calls = $25$, with an average talk time of $90\text{s}$ and a ringing window of $20\text{s}$.
3. By Little's Law / Poisson departure rates, expected agents freeing during the ring window:
   $$E[\text{freeing}] = 25 \times \left(\frac{20}{90}\right) = 5.5 \text{ agents}.$$
4. Total expected capacity at answer time = $5 + 5.5 = 10.5 \text{ agents}$.
5. Historical answer rate is $55\%$.
6. To connect $10.5$ agents at a $55\%$ answer rate with $2$ calls already ringing in-flight:
   $$\text{Calls to Dial} = \frac{10.5 - (2 \times 0.55)}{0.55} = \frac{9.4}{0.55} \approx 17.1 \longrightarrow \mathbf{17 \text{ calls}}.$$
Every pacing response returns this exact factor breakdown in the audit log.

---

### Q7: What part of your architecture are you least confident about?
**Answer:**
The assumption of **stationary average talk time** during abrupt operational shifts (e.g. when high-balance contentious borrowers answer, average call duration doubles from 90s to 180s).
While our Poisson departure model accounts for mean duration, extreme variance in talk time can delay agent release.
*Production Solution*: Integrate real-time call transcript milestone tracking (e.g. wrap-up signal detection via Voice AI) to predict agent availability before the call officially terminates.

---

## 8. Documentation Index

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): Full component diagrams, agent state machine, call state machine.
- [docs/ADR.md](docs/ADR.md): Architecture Decision Records (Safety Controller, SQLite WAL vs Postgres, Little's Law).
- [docs/FAILURES_AND_RECOVERY.md](docs/FAILURES_AND_RECOVERY.md): Comprehensive analysis of all 7 failure scenarios.
- [docs/SCALING_100_1000_10000.md](docs/SCALING_100_1000_10000.md): Distributed systems scaling bottlenecks and fixes.
- [docs/FINAL_QUESTION.md](docs/FINAL_QUESTION.md): In-depth architectural answer to the prompt's final question.
- [docs/API.md](docs/API.md): Full REST API specification with request/response schemas.

---

## 9. License & Submission
Developed for CredResolve Technical Hiring Evaluation 2026.
Author: Candidate (Senior Full Stack & Distributed Systems Engineer).
