"""
state routes (v1)

these endpoints let us:
- set shift / patient list once
- add/remove orders as the "shift" evolves
- replan the schedule without resending the entire payload

this is a backend leap because it introduces:
- state
- mutation endpoints
- basic consistency checks
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.state import get_context, reset_context
from app.schemas.clinical import (
    Order,
    Patient,
    ScheduleRequest,
    ScheduleResponse,
    Shift,
)
from app.services.scheduler import generate_schedule

router = APIRouter(prefix="/state")


class StateResponse(BaseModel):
    """
    What we return when someone asks for current state.
    Keeping it explicit makes /docs easier to understand.
    """
    shift: Optional[Shift]
    patients: list[Patient]
    orders: list[Order]
    updated_at: str


@router.get("", response_model=StateResponse)
def get_state() -> StateResponse:
    """
    Returns the current in-memory state.

    This is basically our "debug dashboard" for the backend.
    If something looks wrong, check /state first.
    """
    ctx = get_context()
    return StateResponse(
        shift=ctx.shift,
        patients=ctx.patients,
        orders=ctx.orders,
        updated_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    )


@router.post("/reset", status_code=status.HTTP_204_NO_CONTENT)
def reset_state() -> None:
    """
    Resets state for demos and dev work.

    Example:
    - teammate tries stuff
    - state gets messy
    - reset and start clean
    """
    reset_context()


@router.post("/shift", response_model=Shift)
def set_shift(shift: Shift) -> Shift:
    """
    Sets the shift window in state.

    We require a valid window here so downstream scheduling doesn't have to guess.
    """
    if shift.end_at <= shift.start_at:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid shift window: end_at must be after start_at.",
        )

    ctx = get_context()
    ctx.shift = shift
    return shift


@router.post("/patients", response_model=list[Patient])
def set_patients(patients: list[Patient]) -> list[Patient]:
    """
    Replaces the current patient list.

    Why replace instead of patching:
    - simpler mental model
    - the patient assignment for a shift is usually a set
    - we can add patch endpoints later if needed
    """
    # Basic sanity: IDs should be unique
    ids = [p.id for p in patients]
    if len(ids) != len(set(ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Patient IDs must be unique.",
        )

    ctx = get_context()
    ctx.patients = patients

    # Optional cleanup:
    # If we removed a patient, any orders referencing them become invalid.
    # For v1, we filter those orders out so state stays consistent.
    patient_ids = set(ids)
    ctx.orders = [o for o in ctx.orders if o.patient_id in patient_ids]

    return patients


@router.post("/orders", response_model=Order, status_code=status.HTTP_201_CREATED)
def add_order(order: Order) -> Order:
    """
    Adds a single order to state.

    This simulates "new order placed" during the shift.
    """
    ctx = get_context()

    if not ctx.has_patient(order.patient_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unknown patient_id '{order.patient_id}'. Add the patient first via POST /state/patients.",
        )

    # Enforce unique order IDs so delete/update is unambiguous.
    if any(o.id == order.id for o in ctx.orders):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Order with id '{order.id}' already exists.",
        )

    ctx.orders.append(order)
    return order


@router.delete("/orders/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(order_id: str) -> None:
    """
    Removes an order from state.

    This simulates:
    - order discontinued
    - order completed and no longer needs scheduling
    """
    ctx = get_context()
    before = len(ctx.orders)
    ctx.orders = [o for o in ctx.orders if o.id != order_id]

    if len(ctx.orders) == before:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Order '{order_id}' not found.",
        )


@router.post("/replan", response_model=ScheduleResponse)
def replan() -> ScheduleResponse:
    """
    Generates a schedule using whatever is currently in state.

    This is the main win:
    - shift/patients set once
    - orders can change over time
    - we can regenerate a schedule without re-sending everything
    """
    ctx = get_context()

    if ctx.shift is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Shift not set. Use POST /state/shift first.",
        )

    # We build the same ScheduleRequest the stateless endpoint expects.
    req = ScheduleRequest(
        shift=ctx.shift,
        patients=ctx.patients,
        orders=ctx.orders,
    )

    return generate_schedule(req)