from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class AcuityLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class OrderType(str, Enum):
    medication = "medication"
    procedure = "procedure"
    lab = "lab"
    assessment = "assessment"


class Order(BaseModel):
    id: str
    patient_id: str
    type: OrderType
    description: str
    due_at: datetime
    duration_minutes: int = Field(default=10, ge=1, le=240)
    is_prn: bool = False
    is_stat: bool = False


class Patient(BaseModel):
    id: str
    display_name: str
    acuity: AcuityLevel


class Shift(BaseModel):
    start_at: datetime
    end_at: datetime


class ScheduleRequest(BaseModel):
    shift: Shift
    patients: list[Patient]
    orders: list[Order]


class ScheduledTask(BaseModel):
    order_id: str
    patient_id: str
    starts_at: datetime
    ends_at: datetime
    priority_score: float
    rationale: str


class ScheduleResponse(BaseModel):
    order_id: str
    patient_id: str
    patient_display_name: str

    starts_at: datetime
    ends_at: datetime

    priority_score: float

    # short sentence meant to be read by a human
    summary: str

    # structured explanation meant for transparency and debugging
    score_breakdown: ScoreBreakdown
    
class ScoreBreakdown(BaseModel):
    """
    Structured explanation of why an order was prioritized.

    This exists so:
    - humans can understand decisions
    - teammates can debug scoring logic
    - future ML models can explain themselves in the same format
    """
    acuity: str
    order_type: str
    due_in_minutes: float
    urgency: float
    is_stat: bool
    is_prn: bool    