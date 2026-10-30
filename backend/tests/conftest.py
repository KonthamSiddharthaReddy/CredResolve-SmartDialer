import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models import Agent, Borrower, Campaign
from backend.app.models.enums import AgentState, BorrowerStatus, DialingMode, ProviderType

@pytest.fixture(scope="function")
def db_session():
    # Use in-memory SQLite with static pool for test isolation
    from sqlalchemy.pool import StaticPool
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    # Seed test campaign
    camp = Campaign(
        id=1,
        name="Test Campaign",
        dialing_mode=DialingMode.PROGRESSIVE.value,
        provider_type=ProviderType.PROVIDER_A.value,
        is_active=True,
        target_abandon_rate=0.01,
        avg_talk_time_seconds=90.0,
        avg_ring_time_seconds=15.0,
        historical_answer_rate=0.50
    )
    session.add(camp)
    session.commit()

    yield session

    session.close()
    Base.metadata.drop_all(bind=engine)
