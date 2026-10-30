from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any
from backend.app.models.enums import DialingMode

@dataclass
class PacingDecision:
    mode: DialingMode
    requested_calls: int
    metrics: Dict[str, Any] = field(default_factory=dict)
    rationale: str = ""

class BasePacingEngine(ABC):
    @abstractmethod
    def calculate_pacing(
        self,
        available_agents: int,
        connected_calls: int,
        ringing_calls: int,
        wrap_up_agents: int,
        historical_answer_rate: float,
        avg_talk_time_sec: float,
        avg_ring_time_sec: float,
        provider_latency_sec: float,
        provider_failure_rate: float
    ) -> PacingDecision:
        pass
