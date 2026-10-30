# Load Test Benchmark Results

Executed on: 2026-10-30T07:30:57.487247+00:00
Architecture: Python 3.12, SQLite WAL mode, SQLAlchemy 2.0 with Optimistic Concurrency Control

---

## 1. Summary of Benchmark Runs

| Benchmark Name | Requests | Total Time | Throughput | Mean Latency | p50 | p95 | p99 | Double Allocations | Invariant Status |
|---|---|---|---|---|---|---|---|---|---|
| **Concurrent Agent Allocation** | 150 | 1.042s | **143.9 ops/s** | 78.61ms | 3.41ms | 619.06ms | 963.49ms | **0** | **PASS** |
| **Concurrent Borrower Allocation** | 250 | 1.758s | **142.2 ops/s** | 89.81ms | 3.5ms | 916.94ms | 1598.33ms | **0** | **PASS** |

---

## 2. Invariant Verification

1. **Zero Double Allocation (Agent Safety)**:
   - Evaluated under 20 concurrent threads attempting atomic reservation on a shared agent pool.
   - Result: Exactly 0 double-reservations. Every allocated agent was unique.
   - Status: **PASS**

2. **Zero Double Allocation (Borrower Safety)**:
   - Evaluated under 20 concurrent threads attempting reservation on a shared borrower queue.
   - Result: Exactly 0 double-reservations. Every allocated borrower was unique.
   - Status: **PASS**

3. **Concurrency Contention Handling**:
   - When multiple workers contended for the same top-row candidate, SQLite WAL mode serialized write commits while conditional `WHERE version = :version` updates failed cleanly without throwing database lock exceptions.
   - Workers automatically progressed to the next available candidate.
   - Status: **PASS**
