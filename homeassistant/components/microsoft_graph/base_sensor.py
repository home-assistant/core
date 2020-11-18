"""Base Sensor for the Microsoft Graph Integration."""
from typing import Optional

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import GraphUpdateCoordinator
from .const import DOMAIN


class GraphBaseSensorEntity(CoordinatorEntity):
    """Base Sensor for the Microsoft Graph Integration."""

    def __init__(self, coordinator: GraphUpdateCoordinator, uuid: str, attribute: str):
        """Initialize Microsoft Graph sensor."""
        super().__init__(coordinator)
        self.uuid = uuid
        self.attribute = attribute

    @property
    def unique_id(self) -> str:
        """Return a unique, Home Assistant friendly identifier for this entity."""
        return f"{self.attribute}"

    @property
    def data(self) -> Optional[dict]:
        """Return coordinator data for this user."""
        return self.coordinator.data.presence.get(self.uuid)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        if not self.data:
            return None

        return " ".join([part.title() for part in self.attribute.split("_")])

    @property
    def entity_registry_enabled_default(self) -> bool:
        """Return if the entity should be enabled when first added to the entity registry."""
        return True

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, "microsoft_graph")},
            "name": "Microsoft Graph",
            "manufacturer": "Microsoft",
            "model": "Microsoft Graph",
            "entry_type": "service",
        }
