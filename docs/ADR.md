# Architecture Decision Records (ADR)

## ADR 001: Independent Safety Controller as an Unbypassable Gatekeeper

### Context
In automated outbound dialing for debt recovery and collections, abandoned connected calls (borrower answers but no collection agent is free within 2 seconds) are severe regulatory violations (e.g. FTC, FCC, RBI, and UK Ofcom regulations dictate maximum abandonment thresholds of 1% to 3%). Predictive pacing engines use statistical models that can be wrong during abrupt carrier disruptions or sudden agent departures.

### Decision
We decoupled the pacing calculation from call execution by introducing a mandatory, independent **Safety Controller**.
The pipeline is strictly:
$$\text{Campaign} \longrightarrow \text{Pacing Engine} \longrightarrow \mathbf{\text{Safety Controller}} \longrightarrow \text{Call Allocator} \longrightarrow \text{Telecom Provider}$$
The predictive algorithm has **no interface or permissions** to place calls directly or bypass the Safety Controller.
The controller enforces:
- Hard rejection when agents are missing.
- Dynamic clamping when overdial requests exceed risk-adjusted safety thresholds.
- Automatic fallback to 1:1 Progressive Dialing upon any observed abandoned call, circuit breaker trip, or answer rate collapse.

### Consequences
- **Positive**: Zero possibility of runaway speculative dialing. Strict compliance guarantee.
- **Trade-off**: In highly volatile scenarios, maximum agent utilization is slightly throttled in favor of deterministic call safety.

---

## ADR 002: Concurrency Strategy – SQLite WAL & Optimistic Versioning vs. PostgreSQL Row Locking

### Context
When multiple worker processes or asynchronous tasks query the database for available agents or queued borrowers, race conditions can cause two workers to reserve the same agent or dial the same borrower simultaneously.

### Decision
For the local prototype, we implemented **SQLite with WAL Mode** (`PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`) coupled with **Optimistic Concurrency Control via Version Columns**:
```sql
UPDATE agents 
SET status = 'RESERVED', reserved_at = :now, version = version + 1 
WHERE id = :id AND status = 'AVAILABLE' AND version = :version;
```
If `rowcount == 0`, another worker reserved the agent milliseconds prior; the worker rolls back and selects the next candidate.

### Production Scaling Path (PostgreSQL)
For production deployments (1,000 to 10,000 agents), optimistic concurrency causes retry thrashing under high lock contention. In PostgreSQL, we transition to **Pessimistic Row Locking with `SKIP LOCKED`**:
```sql
SELECT id 
FROM agents 
WHERE status = 'AVAILABLE' 
ORDER BY last_status_change ASC 
LIMIT 1 
FOR UPDATE SKIP LOCKED;
```
This enables hundreds of concurrent dialer workers to grab mutually exclusive available agents with zero locking contention or serialized deadlocks.

---

## ADR 003: Statistical Predictive Pacing Engine based on Little's Law

### Context
The assignment specifically requested an explainable statistical or rule-based predictive model rather than an opaque black-box machine learning model.

### Decision
We formulated the predictive engine using **Little's Law** and Poisson departure rates:
1. Average call duration ($T_{talk}$) and ringing setup window ($T_{ring} + L_{provider}$).
2. Expected freeing agents during the ring window:
   $$E[\text{freeing}] = C_{conn} \times \left(\frac{T_{ring} + L_{provider}}{T_{talk}}\right) + A_{wrap} \times 0.8$$
3. Projected capacity:
   $$C_{exp} = A_{avail} + E[\text{freeing}]$$
4. Calls required given effective answer rate $p_{eff}$:
   $$\text{Raw Target} = \frac{\max\left(0, C_{exp} - (C_{ring} \times p_{eff})\right)}{p_{eff}}$$
5. Statistical damping factor ($0.90$) applied to account for binomial variance ($\sigma = \sqrt{N p (1-p)}$).

### Consequences
- Every pacing decision generates a plain-text mathematical rationale stored in the audit database and displayed on the UI.
- Explainability is 100%, allowing engineers and compliance auditors to inspect why $N$ calls were initiated.

---

## ADR 004: Dual Mock Telecom Providers with Chaos Injection & Circuit Breakers

### Context
Real telecom providers experience latency jitter, carrier drops, timeouts, duplicate webhooks, and out-of-order events. Testing resilience requires differing provider behaviors without paid third-party dependencies.

### Decision
We implemented a shared `ITelecomProvider` interface with two implementations:
- **Provider A (ReliableTelecom)**: 50–150ms latency, 98%+ reliability, clean event sequencing.
- **Provider B (FlakyTelecom)**: 400–1500ms latency, 10% timeouts, duplicate `ANSWERED` events, and out-of-order `COMPLETED` webhooks.
- **Circuit Breaker**: Each provider incorporates a 3-state circuit breaker (`CLOSED`, `OPEN`, `HALF_OPEN`). When rolling failure rate exceeds 40%, the circuit trips to `OPEN`, triggering Safety Controller fallback.


---

## ADR 005: Replacement of Arbitrary Overdial Multiplier with Binomial Upper Confidence Limit (UCL) Ceiling

### Context
Static overdial multipliers (such as an arbitrary $3.0\times$ capacity factor) are statistically indefensible in regulated collections environments:
- When answer rate is high ($p = 0.70$), dialing $3.0\times$ capacity expects $2.1\times$ live answers, mathematically guaranteeing severe call abandonment.
- When answer rate is low ($p = 0.15$), a $3.0\times$ multiplier yields only $0.45\times$ expected answers, artificially suppressing agent utilization.

### Decision
We replaced arbitrary static multipliers with an inverted **Binomial Upper Confidence Limit (UCL)** safety ceiling.
Given expected capacity $C_{\text{target}} = A_{avail} + E[\text{freeing}]$ and target abandonment risk tolerance $\alpha = 0.01$ (1%), the Safety Controller bounds $P(\text{Answers} > C_{\text{target}}) \le \alpha$.
Using the inverted Normal approximation to $B(N, p)$:
$$C_{\text{target}} \ge N p + z_{1-\alpha} \sqrt{N p (1 - p)}$$
Solving the quadratic in $u = \sqrt{N}$ yields the exact safe dialing ceiling:
$$u_{\text{safe}} = \frac{-z_{1-\alpha} \sqrt{p(1-p)} + \sqrt{z_{1-\alpha}^2 p(1-p) + 4 p C_{\text{target}}}}{2p}$$
$$N_{\text{safe}} = \max\left(A_{avail}, \lfloor u_{\text{safe}}^2 \rfloor\right)$$

### Consequences
- **Statistical Defensibility**: The ceiling automatically contracts when answer rates are high (preventing abandon spikes) and expands when answer rates are low (preserving utilization).
- **Compliance Alignment**: Formally ensures the probability of call abandonment remains bounded under $1\%$.
