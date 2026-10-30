import os
from pydantic import BaseModel
from typing import Optional

class Settings(BaseModel):
    PROJECT_NAME: str = "CredResolve SmartDialer"
    API_V1_STR: str = "/api/v1"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./smartdialer.db")
    
    # Safety Controller constraints
    MAX_ABANDON_RATE_TOLERANCE: float = 0.01  # Max 1% abandon rate (regulatory threshold)
    MAX_OVERDIAL_RATIO: float = 3.0           # Maximum multiplier over expected capacity
    RESERVATION_TTL_SECONDS: int = 10         # TTL for agent/borrower reservations
    CALL_INITIATION_TIMEOUT_SECONDS: int = 45 # Timeout for in-flight calls without provider updates
    DEFAULT_AVG_TALK_TIME_SECONDS: int = 90
    DEFAULT_AVG_RING_TIME_SECONDS: int = 20
    
    # Circuit Breaker defaults
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: float = 0.40  # 40% errors triggers circuit breaker
    CIRCUIT_BREAKER_WINDOW_SIZE: int = 20           # Rolling window of last N calls
    CIRCUIT_BREAKER_COOLDOWN_SECONDS: int = 15      # Time before attempting HALF-OPEN
    
    # Simulation speedup factor
    SIMULATION_TIME_SCALE: float = 1.0

settings = Settings()
