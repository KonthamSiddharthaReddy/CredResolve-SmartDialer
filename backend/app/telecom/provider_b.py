import asyncio
import random
import uuid
import time
from typing import Dict, Any, List
from backend.app.telecom.interface import ITelecomProvider, ProviderCallResult
from backend.app.telecom.circuit_breaker import CircuitBreaker

class ProviderB(ITelecomProvider):
    """
    Provider B (FlakyTelecom):
    - Slower responses (~400-1500ms)
    - Occasional timeouts
    - Duplicate events
    - Out-of-order events
    - Can simulate severe degradation
    """
    def __init__(self):
        self.name = "PROVIDER_B"
        self.circuit_breaker = CircuitBreaker(name="PROVIDER_B", failure_threshold=0.40, window_size=20, cooldown_seconds=10.0)
        self.base_latency_ms = 600.0
        self.timeout_rate = 0.10
        self.duplicate_event_rate = 0.25
        self.out_of_order_rate = 0.15
        self.force_outage = False
        self.force_timeouts = False

    async def initiate_call(self, call_id: int, phone: str, idempotency_key: str) -> ProviderCallResult:
        start_time = time.time()

        # Check circuit breaker
        if not self.circuit_breaker.can_execute():
            return ProviderCallResult(
                success=False,
                error_message="Provider B Circuit Breaker is OPEN",
                latency_ms=2.0,
                is_timeout=False
            )

        # Higher latency with heavy jitter
        jitter = random.uniform(-200, 800)
        simulated_delay = max(0.05, (self.base_latency_ms + jitter) / 1000.0)
        
        # Check if forced outage or timeout
        if self.force_outage or self.force_timeouts or random.random() < self.timeout_rate:
            # Simulate waiting then timing out
            await asyncio.sleep(min(simulated_delay, 0.4))
            latency_ms = (time.time() - start_time) * 1000.0
            self.circuit_breaker.record_failure("Provider B Request Timeout / Connection Reset")
            return ProviderCallResult(
                success=False,
                error_message="Provider B Gateway Timeout (HTTP 504)",
                latency_ms=latency_ms,
                is_timeout=True
            )

        await asyncio.sleep(simulated_delay)
        latency_ms = (time.time() - start_time) * 1000.0
        self.circuit_breaker.record_success(latency_ms)

        provider_call_id = f"PB-{call_id}-{uuid.uuid4().hex[:8]}"
        return ProviderCallResult(
            success=True,
            provider_call_id=provider_call_id,
            latency_ms=latency_ms
        )

    async def hangup(self, provider_call_id: str) -> bool:
        await asyncio.sleep(0.1)
        return True

    def should_emit_duplicate_answered(self) -> bool:
        return random.random() < self.duplicate_event_rate

    def should_emit_out_of_order(self) -> bool:
        return random.random() < self.out_of_order_rate

    def get_health(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "circuit": self.circuit_breaker.get_metrics(),
            "avg_latency_ms": self.base_latency_ms,
            "timeout_rate": self.timeout_rate,
            "duplicate_event_rate": self.duplicate_event_rate,
            "out_of_order_rate": self.out_of_order_rate,
            "is_outage_forced": self.force_outage
        }
