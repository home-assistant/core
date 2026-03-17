"""Sensor platform for AuroraWatch UK integration."""

import logging
from typing import cast

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
    coordinator = cast(
        AurowatchDataUpdateCoordinator,
        hass.data[DOMAIN][entry.entry_id],
    )
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
    def native_value(self) -> str | None:
        """Return the state of the sensor."""
        if self.coordinator.data:
            return self.coordinator.data.get("status")
        return None

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        data = self.coordinator.data or {}
        return {
            ATTR_LAST_UPDATED: data.get("last_updated"),
            ATTR_PROJECT_ID: data.get("project_id"),
            ATTR_SITE_ID: data.get("site_id"),
            ATTR_SITE_URL: data.get("site_url"),
            ATTR_API_VERSION: data.get("api_version"),
        }


class AurowatchActivitySensor(AurowatchEntity, SensorEntity):
    """Representation of an AuroraWatch geomagnetic activity sensor."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "nT"

    def __init__(self, coordinator: AurowatchDataUpdateCoordinator) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, "geomagnetic_activity")

    @property
    def native_value(self) -> int | float | None:
        """Return the geomagnetic activity value."""
        if self.coordinator.data:
            return self.coordinator.data.get("activity")
        return None
