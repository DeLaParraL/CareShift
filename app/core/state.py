"""
in-memory state store (v1)

why this exists:
right now our /schedule/generate endpoint is stateless.
that is good for purity, but annoying for real workflows and collaboration because
you have to paste the full payload every time.

this module creates a simple in-memory "shift context" that holds:
- shift window
- patients
- orders

important limitations (v1):
- in-memory only, so it resets when the server restarts
- single global state (not per-user)
- no auth

this is intentionally a stepping stone.
once the API feels right, we can replace this store with sqlite/postgres/etc
without rewriting the scheduler logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from app.schemas.clinical import Order, Patient, Shift


@dataclass
class ShiftContext:
    """
    Represents the working set of data for one scheduling run.

    Think of this as:
    "what the nurse knows right now about their shift assignment"
    """
    shift: Optional[Shift] = None
    patients: list[Patient] = field(default_factory=list)
    orders: list[Order] = field(default_factory=list)

    def patients_by_id(self) -> dict[str, Patient]:
        return {p.id: p for p in self.patients}

    def has_patient(self, patient_id: str) -> bool:
        return any(p.id == patient_id for p in self.patients)


# Single global store (v1)
# This is the simplest thing that works for local dev + teammates testing endpoints.
_CONTEXT = ShiftContext()


def get_context() -> ShiftContext:
    """
    Returns the singleton context object.

    We keep it behind a function so:
    - later we can swap it for a DB-backed implementation
    - routers don't need to care where state comes from
    """
    return _CONTEXT


def reset_context() -> None:
    """
    Resets the singleton context.
    Useful for demos, tests, and team iteration.
    """
    global _CONTEXT
    _CONTEXT = ShiftContext()