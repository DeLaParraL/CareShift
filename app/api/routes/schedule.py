from fastapi import APIRouter
from app.schemas.clinical import ScheduleRequest, ScheduleResponse
from app.services.scheduler import generate_schedule

router = APIRouter()

@router.post("/schedule/generate", response_model=ScheduleResponse)
def schedule_generate(req: ScheduleRequest):
    return generate_schedule(req)