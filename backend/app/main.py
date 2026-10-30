import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import select
from backend.app.config import settings
from backend.app.database import engine, SessionLocal, Base
from backend.app.models import Campaign, Agent, Borrower
from backend.app.models.enums import AgentState, BorrowerStatus, DialingMode, ProviderType
from backend.app.api.agents import router as agents_router
from backend.app.api.campaigns import router as campaigns_router
from backend.app.api.calls import router as calls_router
from backend.app.api.dialer import router as dialer_router
from backend.app.api.simulation import router as simulation_router
from backend.app.api.webhooks import router as webhooks_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SmartDialer")

def init_db_data():
    """Initializes tables and seeds default data if db is empty"""
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        camp = db.execute(select(Campaign).where(Campaign.id == 1)).scalar_one_or_none()
        if not camp:
            camp = Campaign(
                id=1,
                name="CredResolve Default Campaign",
                dialing_mode=DialingMode.PROGRESSIVE.value,
                provider_type=ProviderType.PROVIDER_A.value,
                is_active=True,
                target_abandon_rate=0.01,
                avg_talk_time_seconds=90.0,
                avg_ring_time_seconds=15.0,
                historical_answer_rate=0.50
            )
            db.add(camp)
            db.commit()
            db.refresh(camp)

            # Seed 50 default agents
            agents = [
                Agent(name=f"Agent-{i:03d}", status=AgentState.AVAILABLE.value)
                for i in range(1, 51)
            ]
            db.add_all(agents)

            # Seed 200 default borrowers
            borrowers = [
                Borrower(
                    name=f"Borrower-{i:04d}",
                    phone=f"+9198765{i:05d}",
                    status=BorrowerStatus.QUEUED.value,
                    priority=(3 if i % 10 == 0 else (2 if i % 3 == 0 else 1)),
                    campaign_id=camp.id
                )
                for i in range(1, 201)
            ]
            db.add_all(borrowers)
            db.commit()
            logger.info("Initialized default campaign, 50 agents, and 200 borrowers.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db_data()
    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="High-Throughput Progressive & Predictive SmartDialer with Independent Safety Controller",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for frontend dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(agents_router, prefix=settings.API_V1_STR)
app.include_router(campaigns_router, prefix=settings.API_V1_STR)
app.include_router(calls_router, prefix=settings.API_V1_STR)
app.include_router(dialer_router, prefix=settings.API_V1_STR)
app.include_router(simulation_router, prefix=settings.API_V1_STR)
app.include_router(webhooks_router, prefix=settings.API_V1_STR)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "database": "connected"
    }

# Serve frontend build if present
frontend_dist_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(frontend_dist_dir):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_dir, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        # Don't intercept API or docs routes
        if full_path.startswith("api") or full_path.startswith("docs") or full_path.startswith("openapi"):
            return None
        index_file = os.path.join(frontend_dist_dir, "index.html")
        return FileResponse(index_file)
else:
    @app.get("/")
    def root():
        return {
            "message": f"Welcome to {settings.PROJECT_NAME}",
            "docs_url": "/docs",
            "api_v1": settings.API_V1_STR
        }
