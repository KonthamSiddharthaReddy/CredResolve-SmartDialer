import time
from collections import deque
from backend.app.models.enums import CircuitState

class CircuitBreaker:
    def __init__(
        self,
        name: str,
        failure_threshold: float = 0.40,
        window_size: int = 20,
        cooldown_seconds: float = 15.0
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.window_size = window_size
        self.cooldown_seconds = cooldown_seconds
        
        self.state = CircuitState.CLOSED
        self.window = deque(maxlen=window_size)  # True for success, False for failure
        self.last_state_change = time.time()
        self.half_open_trials = 0
        self.max_half_open_trials = 3

    def can_execute(self) -> bool:
        now = time.time()
        if self.state == CircuitState.CLOSED:
            return True
        elif self.state == CircuitState.OPEN:
            if now - self.last_state_change >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                self.last_state_change = now
                self.half_open_trials = 0
                self.window.clear()  # Fresh sample window for canary trials
                return True
            return False
        elif self.state == CircuitState.HALF_OPEN:
            if self.half_open_trials < self.max_half_open_trials:
                self.half_open_trials += 1
                return True
            return False
        return False

    def record_success(self, latency_ms: float = 100.0) -> None:
        self.window.append(True)
        if self.state == CircuitState.HALF_OPEN:
            # If all trial calls succeeded, close circuit
            if all(self.window) and len(self.window) >= self.max_half_open_trials:
                self.state = CircuitState.CLOSED
                self.last_state_change = time.time()

    def record_failure(self, reason: str = "") -> None:
        self.window.append(False)
        if self.state == CircuitState.HALF_OPEN:
            # Immediately trip back to OPEN
            self.state = CircuitState.OPEN
            self.last_state_change = time.time()
        elif self.state == CircuitState.CLOSED:
            if len(self.window) >= 5:  # Minimum samples to evaluate
                fail_rate = self.window.count(False) / len(self.window)
                if fail_rate >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change = time.time()

    def trip(self) -> None:
        """Force trip the circuit breaker (for chaos simulation)"""
        self.state = CircuitState.OPEN
        self.last_state_change = time.time()

    def reset(self) -> None:
        """Force reset the circuit breaker"""
        self.state = CircuitState.CLOSED
        self.window.clear()
        self.last_state_change = time.time()

    def get_metrics(self) -> dict:
        total = len(self.window)
        failures = self.window.count(False) if total > 0 else 0
        fail_rate = (failures / total) if total > 0 else 0.0
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_rate": round(fail_rate, 4),
            "window_size": total,
            "seconds_since_state_change": round(time.time() - self.last_state_change, 1)
        }
