"""Models for the AVM FRITZ!SmartHome integration."""
from __future__ import annotations

from typing import TypedDict


class EntityInfo(TypedDict):
    """TypedDict for EntityInfo."""

    name: str
    entity_id: str
    unit: str | None
    device_class: str | None
