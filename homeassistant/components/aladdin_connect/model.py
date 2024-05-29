"""Models for Aladdin connect cover platform."""

from __future__ import annotations

from typing import TypedDict


class GarageDoorData(TypedDict):
    """Aladdin door data."""

    device_id: str
    door_number: int
    name: str
    status: str
    link_status: str
    battery_level: int


class GarageDoor:
    """Aladdin Garage Door Entity."""

    def __init__(self, data: GarageDoorData) -> None:
        """Create `GarageDoor` from dictionary of data."""
        self.device_id = data["device_id"]
        self.door_number = data["door_number"]
        self.unique_id = f"{self.device_id}-{self.door_number}"
        self.name = data["name"]
        self.status = data["status"]
        self.link_status = data["link_status"]
        self.battery_level = data["battery_level"]
