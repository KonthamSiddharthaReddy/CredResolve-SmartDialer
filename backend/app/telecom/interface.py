from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from backend.app.telecom.circuit_breaker import CircuitBreaker

class ProviderCallResult:
    def __init__(
        self,
        success: bool,
        provider_call_id: Optional[str] = None,
        latency_ms: float = 0.0,
        error_message: Optional[str] = None,
        is_timeout: bool = False
    ):
        self.success = success
        self.provider_call_id = provider_call_id
        self.latency_ms = latency_ms
        self.error_message = error_message
        self.is_timeout = is_timeout

class ITelecomProvider(ABC):
    name: str
    circuit_breaker: CircuitBreaker

    @abstractmethod
    async def initiate_call(self, call_id: int, phone: str, idempotency_key: str) -> ProviderCallResult:
        pass

    @abstractmethod
    async def hangup(self, provider_call_id: str) -> bool:
        pass

    @abstractmethod
    def get_health(self) -> Dict[str, Any]:
        pass
