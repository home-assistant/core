"""Support for Launch Library sensors."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import (
    ATTR_AGENCY,
    ATTR_AGENCY_COUNTRY_CODE,
    ATTR_LAUNCH_TIME,
    ATTR_STREAM,
    ATTRIBUTION,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    coordinator = hass.data[DOMAIN]

    sensors = [
        NextLaunchSensor(coordinator, "Next launch"),
    ]

    async_add_entities(sensors, True)


class LLBaseEntity(CoordinatorEntity, SensorEntity):
    """Sensor base entity."""

    def __init__(self, coordinator: DataUpdateCoordinator, name: str) -> None:
        """Initialize a Launch Library entity."""
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}/{name}"

    def get_next_launch(self):
        """Return next launch."""
        return next((launch for launch in self.coordinator.data), None)


class NextLaunchSensor(LLBaseEntity):
    """Representation of the next launch sensor."""

    _attr_icon = "mdi:orbit"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        next_launch = self.get_next_launch()
        return next_launch.name

    @property
    def extra_state_attributes(self):
        """Return the attributes of the sensor."""
        next_launch = self.get_next_launch()
        return {
            ATTR_LAUNCH_TIME: next_launch.net,
            ATTR_AGENCY: next_launch.launch_service_provider.name,
            ATTR_AGENCY_COUNTRY_CODE: next_launch.pad.location.country_code,
            ATTR_STREAM: next_launch.webcast_live,
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
