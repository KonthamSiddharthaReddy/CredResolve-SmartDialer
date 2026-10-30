import time
from backend.app.telecom.circuit_breaker import CircuitBreaker
from backend.app.models.enums import CircuitState

def test_circuit_breaker_flow():
    cb = CircuitBreaker("TestCircuit", failure_threshold=0.40, window_size=10, cooldown_seconds=0.1)
    
    # 1. Starts CLOSED
    assert cb.state == CircuitState.CLOSED
    assert cb.can_execute() is True
    
    # 2. Record 6 failures out of 10 -> failure rate 60% > 40%
    for _ in range(6):
        cb.record_failure("error")
    for _ in range(4):
        cb.record_success(50.0)
        
    assert cb.state == CircuitState.OPEN
    assert cb.can_execute() is False
    
    # 3. Wait for cooldown
    time.sleep(0.15)
    
    # Next call should transition to HALF_OPEN
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # 4. Canary calls succeed -> resets to CLOSED
    for _ in range(3):
        cb.record_success(50.0)
    assert cb.state == CircuitState.CLOSED

def test_circuit_breaker_half_open_failure_reopen():
    cb = CircuitBreaker("TestCircuit2", failure_threshold=0.40, window_size=10, cooldown_seconds=0.1)
    cb.trip()
    assert cb.state == CircuitState.OPEN
    
    time.sleep(0.15)
    assert cb.can_execute() is True
    assert cb.state == CircuitState.HALF_OPEN
    
    # Canary call fails -> immediately reopen
    cb.record_failure("canary failed")
    assert cb.state == CircuitState.OPEN
