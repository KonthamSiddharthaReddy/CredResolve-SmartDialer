from backend.app.models import Agent, Borrower, Campaign, Call
from backend.app.models.enums import AgentState, BorrowerStatus, DialingMode, ProviderType
from backend.app.services.simulation_engine import SimulationEngine

def setup_simulation_db(db, num_agents=20, num_borrowers=50):
    db.query(Call).delete()
    db.query(Agent).delete()
    db.query(Borrower).delete()
    db.commit()

    agents = [Agent(name=f"SimAgent-{i}", status=AgentState.AVAILABLE.value) for i in range(1, num_agents + 1)]
    borrowers = [Borrower(name=f"SimBorrower-{i}", phone=f"+9198765{i:05d}", status=BorrowerStatus.QUEUED.value, campaign_id=1) for i in range(1, num_borrowers + 1)]
    db.add_all(agents)
    db.add_all(borrowers)
    db.commit()

def test_scenario_a_configuration(db_session):
    sim = SimulationEngine()
    res = sim.set_scenario(db_session, "SCENARIO_A", campaign_id=1)
    assert res["scenario"] == "SCENARIO_A"
    assert res["answer_rate"] == 0.20
    assert res["avg_talk_time_sec"] == 120.0

def test_scenario_b_configuration(db_session):
    sim = SimulationEngine()
    res = sim.set_scenario(db_session, "SCENARIO_B", campaign_id=1)
    assert res["scenario"] == "SCENARIO_B"
    assert res["answer_rate"] == 0.50
    assert res["avg_talk_time_sec"] == 90.0

def test_scenario_c_configuration(db_session):
    sim = SimulationEngine()
    res = sim.set_scenario(db_session, "SCENARIO_C", campaign_id=1)
    assert res["scenario"] == "SCENARIO_C"
    assert res["answer_rate"] == 0.70
    assert res["avg_talk_time_sec"] == 180.0

def test_scenario_d_dynamic_wave(db_session):
    sim = SimulationEngine()
    sim.set_scenario(db_session, "SCENARIO_D", campaign_id=1)
    setup_simulation_db(db_session, num_agents=5, num_borrowers=10)
    
    # Tick 3 times
    for _ in range(3):
        sim.tick(db_session, campaign_id=1)
    assert sim.scenario_d_step >= 3

def test_progressive_mode_zero_abandonment_guarantee(db_session):
    """
    Verify that across multiple ticks in progressive mode,
    the system NEVER creates abandoned calls.
    """
    sim = SimulationEngine()
    sim.set_scenario(db_session, "SCENARIO_B", campaign_id=1)
    setup_simulation_db(db_session, num_agents=15, num_borrowers=40)

    # Run 5 simulation ticks
    for _ in range(5):
        sim.tick(db_session, campaign_id=1)

    # Verify zero abandoned calls
    abandoned_count = db_session.query(Call).filter(Call.is_abandoned.is_(True)).count()
    assert abandoned_count == 0
