"""Support for Waze travel time sensor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import WazeTravelTimeCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Waze travel time sensor entry."""
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    coordinator = config_entry.runtime_data

    sensor = WazeTravelTimeSensor(config_entry.entry_id, name, coordinator)

    async_add_entities([sensor], False)


class WazeTravelTimeSensor(CoordinatorEntity[WazeTravelTimeCoordinator], SensorEntity):
    """Representation of a Waze travel time sensor."""

    _attr_attribution = "Powered by Waze"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_suggested_display_precision = 0
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_device_info = DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        name="Waze",
        identifiers={(DOMAIN, DOMAIN)},
        configuration_url="https://www.waze.com",
    )
    _attr_translation_key = "waze_travel_time"

    def __init__(
        self,
        unique_id: str,
        name: str,
        coordinator: WazeTravelTimeCoordinator,
    ) -> None:
        """Initialize the Waze travel time sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name

    @property
    def native_value(self) -> float | None:
        """Return the state of the sensor."""
        if self.coordinator.data is not None:
            return self.coordinator.data.duration
        return None

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.data.duration is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the last update."""
        if self.coordinator.data is None:
            return None

        return {
            "duration": self.coordinator.data.duration,
            "distance": self.coordinator.data.distance,
            "route": self.coordinator.data.route,
            "origin": self.coordinator.data.origin,
            "destination": self.coordinator.data.destination,
        }
