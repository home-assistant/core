"""Base Sensor for the Xbox Integration."""
from typing import Optional

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import PresenceData, XboxUpdateCoordinator
from .const import DOMAIN


class XboxBaseSensorEntity(CoordinatorEntity):
    """Base Sensor for the Xbox Integration."""

    def __init__(self, coordinator: XboxUpdateCoordinator, xuid: str, attribute: str):
        """Initialize Xbox binary sensor."""
        super().__init__(coordinator)
        self.xuid = xuid
        self.attribute = attribute

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self.xuid}_{self.attribute}"

    @property
    def data(self) -> Optional[PresenceData]:
        """Return coordinator data for this console."""
        return self.coordinator.data.presence.get(self.xuid)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if not self.data:
            return None

        if self.attribute == "online":
            return self.data.gamertag

        attr_name = " ".join([part.title() for part in self.attribute.split("_")])
        return f"{self.data.gamertag} {attr_name}"

    @property
    def entity_picture(self) -> str:
        """Return the gamer pic."""
        if not self.data:
            return None

        return self.data.display_pic.replace("&mode=Padding", "")

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return self.attribute == "online"

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, "xbox_live")},
            "name": "Xbox Live",
            "manufacturer": "Microsoft",
            "model": "Xbox Live",
            "entry_type": "service",
        }
