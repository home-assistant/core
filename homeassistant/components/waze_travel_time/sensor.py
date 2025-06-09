"""Support for Waze travel time sensor."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_DESTINATION, CONF_ORIGIN, DEFAULT_NAME, DOMAIN
from .coordinator import WazeTravelTimeCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a Waze travel time sensor entry."""
    name = config_entry.data.get(CONF_NAME, DEFAULT_NAME)
    origin = config_entry.data[CONF_ORIGIN]
    destination = config_entry.data[CONF_DESTINATION]

    coordinator = config_entry.runtime_data

    sensor = WazeTravelTimeSensor(
        config_entry.entry_id, name, origin, destination, coordinator
    )

    async_add_entities([sensor], False)


class WazeTravelTimeSensor(CoordinatorEntity[WazeTravelTimeCoordinator], SensorEntity):
    """Representation of a Waze travel time sensor."""

    _attr_attribution = "Powered by Waze"
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
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
        origin: str,
        destination: str,
        coordinator: WazeTravelTimeCoordinator,
    ) -> None:
        """Initialize the Waze travel time sensor."""
        super().__init__(coordinator)
        self._attr_unique_id = unique_id
        self._attr_name = name
        self._origin = origin
        self._destination = destination
        self.coordinator = coordinator

    async def async_added_to_hass(self) -> None:
        """Handle when the entity is added to Home Assistant."""
        await super().async_added_to_hass()

        if self.coordinator.data is not None:
            duration = self.coordinator.data["duration"]
            self._attr_native_value = round(duration) if duration is not None else None
            self.async_write_ha_state()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        if self.coordinator.data is not None:
            duration = self.coordinator.data["duration"]
            self._attr_native_value = round(duration) if duration is not None else None
            self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the state attributes of the last update."""
        if self.coordinator.data["duration"] is None:
            return None

        return {
            "duration": self.coordinator.data["duration"],
            "distance": self.coordinator.data["distance"],
            "route": self.coordinator.data["route"],
            "origin": self.coordinator.data["origin"],
            "destination": self.coordinator.data["destination"],
        }
