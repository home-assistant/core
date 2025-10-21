"""Shared models for the Level Lock integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LevelLockDevice:
    """Representation of a Level lock device."""

    lock_id: str
    name: str
    is_locked: bool | None
    # Raw state from API for transitional states (e.g. "locking"/"unlocking")
    state: str | None = None
