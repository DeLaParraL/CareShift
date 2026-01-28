"""
CareShift scheduler (v1)

What this file is for
This is the brains of the project right now.

Given:
- a shift window (start and end)
- a list of patients with an acuity level to judge difficuly of tasks and attempt to judge timeframe
- a list of orders (meds, labs, procedures, assessments) with due times

We produce:
- a prioritized timeline of tasks for the nurse to follow
- each task includes a score and a human readable rationale so it is explainable

Important note (and I will repeat this everywhere):
This is a demo and uses simulated data. This is not clinical software. None of the data represented in this project is real. Any parallel
to a real patient is simply coincidence.

Also important:
In healthcare, explainability matters. So in v1 I am intentionally starting with a
deterministic rules based scoring approach before touching ML.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from app.schemas.clinical import (
    AcuityLevel,
    Order,
    OrderType,
    Patient,
    ScheduleRequest,
    ScheduleResponse,
    ScheduledTask,
    ScoreBreakdown,
)


# -------------------------
# Scoring weights (v1)
# -------------------------
# This section is intentionally simple and transparent.
# If I were building this into a real system, these weights would be configurable
# and probably tuned with domain expert feedback, audit logging, and a lot of testing.
#
# The goal right now is to show:
# - I can model the problem
# - I can make reasonable tradeoffs
# - I can explain exactly why a task is getting prioritized


# Higher acuity should raise priority across the board.
# I used a multiplier rather than adding a flat number because I want acuity to
# amplify time sensitivity and order type.
ACUITY_WEIGHT: dict[AcuityLevel, float] = {
    AcuityLevel.low: 1.0,
    AcuityLevel.medium: 1.4,
    AcuityLevel.high: 1.8,
    AcuityLevel.critical: 2.2,
}

# Order type weights are rough and just reflect that meds and procedures are often
# more time sensitive and higher risk if delayed.
TYPE_WEIGHT: dict[OrderType, float] = {
    OrderType.medication: 1.4,
    OrderType.procedure: 1.3,
    OrderType.assessment: 1.2,
    OrderType.lab: 1.1,
}


@dataclass(frozen=True)
class ScoredOrder:
    """
    Small wrapper object so we can keep the order plus its computed score plus
    an explanation string all together.

    This makes later steps (sorting and scheduling) cleaner and easier to test.
    """
    order: Order
    score: float
    summary: str
    breakdown: ScoreBreakdown


def _minutes_until(now: datetime, due_at: datetime) -> float:
    """
    Returns how many minutes until the due time.

    Positive means it is due in the future.
    Zero or negative means it is due now or overdue.

    I keep this as a helper so the math is not duplicated in multiple places.
    """
    return (due_at - now).total_seconds() / 60.0


def _compute_urgency(minutes_until_due: float) -> float:
    """
    Converts time until due into an urgency factor.

    My mental model:
    - If it is overdue, urgency should be high and should climb as it becomes more overdue,
      but not explode infinitely.
    - If it is far away, urgency should be lower.
    - If it is close, urgency should rise.

    This is one of the biggest areas we can iterate later.
    In v1 it is intentionally simple.

    Returns a float where bigger means more urgent.
    """
    if minutes_until_due <= 0:
        # Overdue tasks should surface.
        # I bump the base urgency to 3.0 and then add a small factor based on how overdue it is.
        # I cap it so a wildly overdue task does not dominate everything forever.
        overdue_minutes = abs(minutes_until_due)
        return 3.0 + min(overdue_minutes / 30.0, 2.0)

    # If it is due soon, urgency should be higher.
    # If it is due in 2 hours (120 minutes), urgency is around 1.5.
    # If it is due in 4 hours or more, urgency drops toward the floor.
    return max(0.2, 2.5 - (minutes_until_due / 120.0))


def score_orders(
    now: datetime,
    patients_by_id: dict[str, Patient],
    orders: Iterable[Order],
) -> list[ScoredOrder]:
    """
    Assigns a score to each order so we can sort by priority.

    The score is computed from:
    - patient acuity multiplier
    - order type multiplier
    - urgency factor based on due time
    - a bonus for STAT
    - a small penalty for PRN because PRNs are often conditional (not always needed)

    Notes:
    - In v1, if an order references an unknown patient, I skip it.
      Another valid choice would be raising an error and rejecting the request.
      Skipping is more forgiving for demo mode.
    """
    scored: list[ScoredOrder] = []

    for o in orders:
        p = patients_by_id.get(o.patient_id)
        if p is None:
            # In real life, this would be data quality problem.
            # For demo mode, I skip rather than crash the whole schedule.
            continue

        acuity_factor = ACUITY_WEIGHT[p.acuity]
        type_factor = TYPE_WEIGHT[o.type]

        mins = _minutes_until(now, o.due_at)
        urgency = _compute_urgency(mins)

        # STAT should float to the top.
        # I keep this as an additive bonus so it can break ties even when other factors are close.
        stat_bonus = 1.5 if o.is_stat else 0.0

        # PRN is tricky. Some PRNs are critical, some are not.
        # For v1 I apply a small penalty, not a big one, because I do not want to bury PRNs.
        prn_penalty = 0.4 if o.is_prn else 0.0

        # Score formula (v1)
        # Bigger score means more important.
        score = (acuity_factor * type_factor * urgency) + stat_bonus - prn_penalty

        # Human readable summary:
        # This is the part a nurse or teammate should be able to skim without decoding a bunch of key=value pairs.
        # Example: "procedure for Patient A (acuity: critical, due in ~84m, STAT)"
        summary = (
            f"{o.type.value} for {p.display_name} "
            f"(acuity: {p.acuity.value}, due in ~{mins:.0f}m"
            f"{', STAT' if o.is_stat else ''}"
            f"{', PRN' if o.is_prn else ''})"
        )

        # Structured breakdown:
        # This keeps the decision explainable and debuggable.
        # If a teammate wants to tune weights later, this makes it way easier to see what contributed to the score.
        breakdown = ScoreBreakdown(
            acuity=p.acuity.value,
            order_type=o.type.value,
            due_in_minutes=round(mins, 1),
            urgency=round(urgency, 2),
            is_stat=o.is_stat,
            is_prn=o.is_prn,
        )

        scored.append(
            ScoredOrder(
                order=o,
                score=score,
                summary=summary,
                breakdown=breakdown,
            )
        )

    # Sort order:
    # 1) highest score first
    # 2) if scores tie, earlier due time first
    scored.sort(key=lambda x: (-x.score, x.order.due_at))
    return scored


def generate_schedule(req: ScheduleRequest) -> ScheduleResponse:
    """
    Generates a schedule for a single shift.

    V1 scheduling strategy
    - We score all orders
    - We sort them by score (and due time as a tie breaker)
    - We place tasks onto a timeline sequentially starting at:
        max(shift_start, now)
      This is an intentional choice:
      If the shift started earlier than now, we do not schedule tasks in the past.

    What v1 does NOT do yet (future upgrades)
    - Dependencies (example: draw lab before reviewing result before med change)
    - Parallelism (a nurse can sometimes batch or combine tasks by location)
    - Patient clustering (group tasks per patient to reduce back and forth)
    - Hard clinical constraints (example: infusion checks every X minutes)
    - Manual overrides that persist across re plans
    - Re planning based on live vitals changes or doctors order changes
    - Multiple nurses and assignment distribution (big picture task for the way future)

    Why keep it simple right now
    Because I want a clean baseline that is testable and explainable.
    Then we can layer complexity deliberately instead of building a spaghetti algorithm.
    """
    now = datetime.now(timezone.utc)

    # Build quick lookup for patient info (acuity, name, etc).
    patients_by_id = {p.id: p for p in req.patients}

    scored = score_orders(now=now, patients_by_id=patients_by_id, orders=req.orders)

    shift_start = req.shift.start_at
    shift_end = req.shift.end_at

   # cursor is "where we are" in the timeline when placing tasks.
#
# we want behavior that makes sense for both:
# - a live, in-progress shift (start at now, because we can't schedule in the past)
# - a future shift (start at shift_start, because that's what the request asked for)
#
# this keeps demos intuitive and keeps real-world behavior reasonable.
    cursor = shift_start if now < shift_start else now

    tasks: list[ScheduledTask] = []
    notes: list[str] = []

    # Basic validation.
    # If shift times are invalid, fail fast.
    if shift_end <= shift_start:
        return ScheduleResponse(
            generated_at=now,
            tasks=[],
            notes=["Invalid shift window: end_at must be after start_at."],
        )

    # If we are already past the shift end, there is nothing to schedule.
    if cursor >= shift_end:
        return ScheduleResponse(
            generated_at=now,
            tasks=[],
            notes=["Shift window has already ended relative to current time."],
        )

    for item in scored:
        o = item.order

        # If we have no more room in the shift, stop.
        if cursor >= shift_end:
            notes.append("Shift is full. Remaining tasks could not be scheduled.")
            break

        # For v1, we do not try to place tasks exactly at due time.
        # We are creating a prioritized plan, not a strict timed calendar.
        # The nurse can still adjust the timeline.
        #
        # That said, we still respect the shift window boundaries.
        start = cursor
        end = start + timedelta(minutes=o.duration_minutes)

        # If placing this task would exceed the shift, stop.
        # Another approach would be "truncate" or "place partially" but that is not realistic here.
        if end > shift_end:
            notes.append(
                "A task would exceed shift end. Stopping schedule generation."
            )
            break

               # We want the response to be readable without needing to cross-reference IDs,
        # so we include the patient display name too.
        patient = patients_by_id.get(o.patient_id)

        tasks.append(
            ScheduledTask(
                order_id=o.id,
                patient_id=o.patient_id,
                patient_display_name=patient.display_name if patient else "Unknown patient",
                starts_at=start,
                ends_at=end,
                priority_score=item.score,
                summary=item.summary,
                score_breakdown=item.breakdown,
            )
        )

        # Move the cursor forward.
        cursor = end

    return ScheduleResponse(
        generated_at=now,
        tasks=tasks,
        notes=notes,
    )

