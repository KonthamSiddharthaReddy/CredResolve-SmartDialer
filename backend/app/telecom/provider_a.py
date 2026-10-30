import asyncio
import random
import uuid
import time
from typing import Dict, Any
from backend.app.telecom.interface import ITelecomProvider, ProviderCallResult
from backend.app.telecom.circuit_breaker import CircuitBreaker

class ProviderA(ITelecomProvider):
    """
    Provider A (ReliableTelecom):
    - Fast responses (~50-150ms)
    - High reliability (>98% success)
    - Low failure rate
    - Well-behaved event sequencing
    """
    def __init__(self):
        self.name = "PROVIDER_A"
        self.circuit_breaker = CircuitBreaker(name="PROVIDER_A", failure_threshold=0.35, window_size=20)
        self.base_latency_ms = 80.0
        self.failure_rate = 0.02
        self.force_outage = False

    async def initiate_call(self, call_id: int, phone: str, idempotency_key: str) -> ProviderCallResult:
        start_time = time.time()
        
        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            return ProviderCallResult(
                success=False,
                error_message="Provider A Circuit Breaker is OPEN",
                latency_ms=1.0,
                is_timeout=False
            )

        # Simulate network latency
        jitter = random.uniform(-20, 40)
        simulated_delay = max(0.01, (self.base_latency_ms + jitter) / 1000.0)
        await asyncio.sleep(simulated_delay)
        latency_ms = (time.time() - start_time) * 1000.0

        if self.force_outage or random.random() < self.failure_rate:
            self.circuit_breaker.record_failure("Provider A simulated network fault")
            return ProviderCallResult(
                success=False,
                error_message="Provider A gateway error",
                latency_ms=latency_ms,
                is_timeout=False
            )

        self.circuit_breaker.record_success(latency_ms)
        provider_call_id = f"PA-{call_id}-{uuid.uuid4().hex[:8]}"
        return ProviderCallResult(
            success=True,
            provider_call_id=provider_call_id,
            latency_ms=latency_ms
        )

    async def hangup(self, provider_call_id: str) -> bool:
        await asyncio.sleep(0.02)
        return True

    def get_health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "circuit": self.circuit_breaker.get_metrics(),
            "avg_latency_ms": self.base_latency_ms,
            "is_outage_forced": self.force_outage
        }
