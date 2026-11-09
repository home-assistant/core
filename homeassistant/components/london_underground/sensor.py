"""Sensor for checking the status of London Underground tube lines."""

import logging
from typing import Any, override

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, DOMAIN
from .coordinator import LondonTubeCoordinator, LondonUndergroundConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LondonUndergroundConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the London Underground sensor from config entry."""

    async_add_entities(
        LondonTubeSensor(entry.runtime_data, line) for line in entry.options[CONF_LINE]
    )


class LondonTubeSensor(CoordinatorEntity[LondonTubeCoordinator], SensorEntity):
    """Sensor that reads the status of a line from Tube Data."""

    _attr_attribution = "Powered by TfL Open Data"
    _attr_icon = "mdi:subway"
    _attr_has_entity_name = True  # Use modern entity naming

    def __init__(self, coordinator: LondonTubeCoordinator, name: str) -> None:
        """Initialize the London Underground sensor."""
        super().__init__(coordinator)
        self._name = name
        # Add unique_id for proper entity registry
        self._attr_unique_id = f"tube_{name.lower().replace(' ', '_')}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, DOMAIN)},
            name="London Underground",
            manufacturer="Transport for London",
            model="Tube Status",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    @override
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    @override
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data[self.name]["State"]

    @property
    @override
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details about the sensor state."""
        return {"Description": self.coordinator.data[self.name]["Description"]}
