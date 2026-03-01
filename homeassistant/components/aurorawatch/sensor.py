"""Sensor platform for AuroraWatch UK integration."""

import logging

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ATTR_API_VERSION,
    ATTR_LAST_UPDATED,
    ATTR_PROJECT_ID,
    ATTR_SITE_ID,
    ATTR_SITE_URL,
    DOMAIN,
)
from .coordinator import AurowatchDataUpdateCoordinator
from .entity import AurowatchEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AuroraWatch sensor."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            AurowatchSensor(coordinator),
            AurowatchActivitySensor(coordinator),
        ]
    )


class AurowatchSensor(AurowatchEntity, SensorEntity):
    """Representation of an AuroraWatch status sensor."""

    def __init__(self, coordinator: AurowatchDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "aurora_status")

    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("status")
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        if not self.coordinator.data:
            return {}

        return {
            ATTR_LAST_UPDATED: self.coordinator.data.get("last_updated"),
            ATTR_PROJECT_ID: self.coordinator.data.get("project_id"),
            ATTR_SITE_ID: self.coordinator.data.get("site_id"),
            ATTR_SITE_URL: self.coordinator.data.get("site_url"),
            ATTR_API_VERSION: self.coordinator.data.get("api_version"),
        }


class AurowatchActivitySensor(AurowatchEntity, SensorEntity):
    """Representation of an AuroraWatch geomagnetic activity sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "nT"

    def __init__(self, coordinator: AurowatchDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "geomagnetic_activity")

    @property
    def native_value(self):
        """Return the geomagnetic activity value."""
        if self.coordinator.data:
            return self.coordinator.data.get("activity")
        return None
