"""Models for Aladdin connect cover platform."""

from __future__ import annotations

from typing import TypedDict


class DoorDevice(TypedDict):
    """Aladdin door device."""

    device_id: str
    door_number: int
    name: str
    status: str
    serial: str
    model: str
