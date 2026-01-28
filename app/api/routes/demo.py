"""
demo routes

this file exists for one reason:
making the project easy to try for other people (teammates, mentors, reviewers).

swagger (/docs) is awesome, but a schedule payload has timestamps.
hardcoding a payload with fixed dates is a trap because the dates go stale fast
and then everything looks "overdue" and confusing.

so this endpoint returns a fresh, valid ScheduleRequest every time:
- shift starts a few minutes from now
- shift ends 12 hours later
- sample patients and sample orders are due during the shift

this is demo and developer-experience focused.
we are NOT calling any real EHRs or using PHI.
"""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter

from app.schemas.clinical import (
    AcuityLevel,
    Order,
    OrderType,
    Patient,
    ScheduleRequest,
    Shift,
)

router = APIRouter()


@router.get("/demo/payload", response_model=ScheduleRequest)
def demo_payload() -> ScheduleRequest:
    """
    returns a sample ScheduleRequest that will work immediately in /docs.

    how to use (in swagger):
    1) call GET /demo/payload and copy the response json
    2) paste it into POST /schedule/generate and hit execute

    why utc:
    - consistent across machines
    - avoids timezone confusion in demos
    - also matches how a lot of backend systems store time internally
    """
    now = datetime.now(timezone.utc)

    # start the shift slightly in the future so that:
    # - due times are positive
    # - the schedule doesn't start in the past
    # - it looks "real" instead of everything being overdue
    shift_start = now + timedelta(minutes=10)
    shift_end = shift_start + timedelta(hours=12)

    # sample patients (fake)
    patients = [
        Patient(id="p1", display_name="Patient A", acuity=AcuityLevel.critical),
        Patient(id="p2", display_name="Patient B", acuity=AcuityLevel.low),
    ]

    # sample orders (fake)
    # we intentionally create 2 orders where one should clearly be prioritized:
    # - critical + stat procedure should come first
    # - routine med should come after
    orders = [
        Order(
            id="o1",
            patient_id="p2",
            type=OrderType.medication,
            description="Routine med (demo)",
            due_at=shift_start + timedelta(minutes=45),
            duration_minutes=10,
            is_prn=False,
            is_stat=False,
        ),
        Order(
            id="o2",
            patient_id="p1",
            type=OrderType.procedure,
            description="Critical stat procedure (demo)",
            due_at=shift_start + timedelta(minutes=90),
            duration_minutes=20,
            is_prn=False,
            is_stat=True,
        ),
    ]

    return ScheduleRequest(
        shift=Shift(start_at=shift_start, end_at=shift_end),
        patients=patients,
        orders=orders,
    )