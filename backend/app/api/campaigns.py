from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.database import get_db
from backend.app.models import Campaign
from backend.app.schemas import CampaignResponse, CampaignCreate, CampaignUpdate

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])

@router.get("", response_model=List[CampaignResponse])
def list_campaigns(db: Session = Depends(get_db)):
    return db.execute(select(Campaign).order_by(Campaign.id.asc())).scalars().all()

@router.get("/{campaign_id}", response_model=CampaignResponse)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return campaign

@router.post("", response_model=CampaignResponse)
def create_campaign(camp_in: CampaignCreate, db: Session = Depends(get_db)):
    campaign = Campaign(
        name=camp_in.name,
        dialing_mode=camp_in.dialing_mode.value,
        provider_type=camp_in.provider_type.value,
        target_abandon_rate=camp_in.target_abandon_rate,
        avg_talk_time_seconds=camp_in.avg_talk_time_seconds,
        avg_ring_time_seconds=camp_in.avg_ring_time_seconds,
        historical_answer_rate=camp_in.historical_answer_rate
    )
    db.add(campaign)
    db.commit()
    db.refresh(campaign)
    return campaign

@router.patch("/{campaign_id}", response_model=CampaignResponse)
def update_campaign(campaign_id: int, update_in: CampaignUpdate, db: Session = Depends(get_db)):
    campaign = db.execute(select(Campaign).where(Campaign.id == campaign_id)).scalar_one_or_none()
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")

    if update_in.dialing_mode is not None:
        campaign.dialing_mode = update_in.dialing_mode.value
    if update_in.provider_type is not None:
        campaign.provider_type = update_in.provider_type.value
    if update_in.is_active is not None:
        campaign.is_active = update_in.is_active
    if update_in.target_abandon_rate is not None:
        campaign.target_abandon_rate = update_in.target_abandon_rate
    if update_in.avg_talk_time_seconds is not None:
        campaign.avg_talk_time_seconds = update_in.avg_talk_time_seconds
    if update_in.avg_ring_time_seconds is not None:
        campaign.avg_ring_time_seconds = update_in.avg_ring_time_seconds
    if update_in.historical_answer_rate is not None:
        campaign.historical_answer_rate = update_in.historical_answer_rate

    db.commit()
    db.refresh(campaign)
    return campaign
