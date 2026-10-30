import concurrent.futures
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from backend.app.database import Base
from backend.app.models import Agent, Borrower
from backend.app.models.enums import AgentState, BorrowerStatus
from backend.app.services.allocation_service import AllocationService

def test_atomic_agent_reservation_race_condition():
    """
    Test two concurrent workers attempting to reserve the exact same agent.
    Only ONE worker must succeed.
    """
    engine = create_engine("sqlite:///./concurrency_test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.query(Agent).delete()
        test_agent = Agent(id=101, name="ConcurrentAgent", status=AgentState.AVAILABLE.value, version=1)
        db.add(test_agent)
        db.commit()

    results = []

    def worker_attempt():
        with Session() as db:
            agent = db.execute(select(Agent).where(Agent.id == 101)).scalar_one()
            success = AllocationService.reserve_agent_atomically(db, agent.id, agent.version)
            return success

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_attempt)
        f2 = executor.submit(worker_attempt)
        results = [f1.result(), f2.result()]

    assert results.count(True) == 1
    assert results.count(False) == 1

    with Session() as db:
        final_agent = db.execute(select(Agent).where(Agent.id == 101)).scalar_one()
        assert final_agent.status == AgentState.RESERVED.value
        assert final_agent.version == 2

    import os
    try:
        os.remove("./concurrency_test.db")
    except Exception:
        pass

def test_atomic_borrower_allocation_race_condition():
    """
    Test two concurrent workers attempting to reserve the same borrower.
    Only ONE worker must succeed.
    """
    engine = create_engine("sqlite:///./concurrency_b_test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.query(Borrower).delete()
        test_borrower = Borrower(id=501, name="ConcurrentBorrower", phone="+919876543210", status=BorrowerStatus.QUEUED.value, version=1)
        db.add(test_borrower)
        db.commit()

    def worker_attempt():
        with Session() as db:
            borrower = db.execute(select(Borrower).where(Borrower.id == 501)).scalar_one()
            success = AllocationService.reserve_borrower_atomically(db, borrower.id, borrower.version)
            return success

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(worker_attempt)
        f2 = executor.submit(worker_attempt)
        results = [f1.result(), f2.result()]

    assert results.count(True) == 1
    assert results.count(False) == 1

    with Session() as db:
        final_borrower = db.execute(select(Borrower).where(Borrower.id == 501)).scalar_one()
        assert final_borrower.status == BorrowerStatus.RESERVED.value
        assert final_borrower.dial_attempts == 1
        assert final_borrower.version == 2

    import os
    try:
        os.remove("./concurrency_b_test.db")
    except Exception:
        pass

def test_multi_worker_pool_allocation_no_double_reservation():
    """
    Simulate 5 concurrent workers attempting to reserve from a pool of 3 available agents.
    Exactly 3 unique agents must be reserved, and 2 workers must get None.
    """
    engine = create_engine("sqlite:///./concurrency_pool_test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.query(Agent).delete()
        agents = [
            Agent(id=201, name="Agent-201", status=AgentState.AVAILABLE.value, version=1),
            Agent(id=202, name="Agent-202", status=AgentState.AVAILABLE.value, version=1),
            Agent(id=203, name="Agent-203", status=AgentState.AVAILABLE.value, version=1),
        ]
        db.add_all(agents)
        db.commit()

    def worker_task():
        with Session() as db:
            reserved = AllocationService.reserve_next_available_agent(db)
            return reserved.id if reserved else None

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(worker_task) for _ in range(5)]
        allocated_ids = [f.result() for f in futures]

    successful_ids = [aid for aid in allocated_ids if aid is not None]
    
    assert len(successful_ids) == 3
    assert len(set(successful_ids)) == 3
    assert set(successful_ids) == {201, 202, 203}
    assert allocated_ids.count(None) == 2

    import os
    try:
        os.remove("./concurrency_pool_test.db")
    except Exception:
        pass

def test_database_transaction_rollback_behaviour():
    """
    Verify database transaction rollback: when a worker encounters an optimistic lock conflict,
    the transaction is rolled back cleanly without creating dirty reads or uncommitted state.
    """
    engine = create_engine("sqlite:///./concurrency_rollback_test.db", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)

    with Session() as db:
        db.query(Agent).delete()
        agent = Agent(id=301, name="RollbackAgent", status=AgentState.AVAILABLE.value, version=1)
        db.add(agent)
        db.commit()

    # Worker 1 successfully updates version to 2
    with Session() as db:
        success = AllocationService.reserve_agent_atomically(db, agent_id=301, current_version=1)
        assert success is True

    # Worker 2 attempts with stale version 1 -> fails and rolls back
    with Session() as db:
        success = AllocationService.reserve_agent_atomically(db, agent_id=301, current_version=1)
        assert success is False
        db.rollback()

    # Verify database state is consistent
    with Session() as db:
        final_agent = db.execute(select(Agent).where(Agent.id == 301)).scalar_one()
        assert final_agent.status == AgentState.RESERVED.value
        assert final_agent.version == 2

    import os
    try:
        os.remove("./concurrency_rollback_test.db")
    except Exception:
        pass
