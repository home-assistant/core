"""Models for Aladdin Connect integration."""

from genie_partner_sdk import GarageDoorData


class AladdinConnectGarageDoor:
    """Data for a Aladdin Connect garage door."""

    def __init__(self, data: GarageDoorData) -> None:
        """Initialize the Aladdin Connect garage door."""

        self.device_id: str = data["device_id"]
        self.door_number: int = data["door_number"]
        self.name: str = data["name"]
        self.status: str | None = data["status"]
        self.battery_level: float | None = data["battery_level"]
        self.link_status: str | None = data["link_status"]
        self.unique_id: str = f"{self.device_id}-{self.door_number}"
