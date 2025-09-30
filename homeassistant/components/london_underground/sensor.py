"""Sensor for checking the status of London Underground tube lines."""

from __future__ import annotations

import logging
from typing import Any

from london_tube_status import TubeData
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    AddEntitiesCallback,
)
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, DEFAULT_LINES, DOMAIN, TUBE_LINES
from .coordinator import LondonTubeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_LINE): vol.All(cv.ensure_list, [vol.In(list(TUBE_LINES))])}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Tube sensor."""

    session = async_get_clientsession(hass)

    data = TubeData(session)
    coordinator = LondonTubeCoordinator(hass, data)

    await coordinator.async_refresh()

    if not coordinator.last_update_success:
        raise PlatformNotReady

    async_add_entities(
        LondonTubeSensor(coordinator, line) for line in config[CONF_LINE]
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the London Underground sensor from config entry."""

    async_add_entities(
        LondonTubeSensor(entry.runtime_data, line)
        for line in entry.options.get(CONF_LINE, DEFAULT_LINES)
    )


class LondonTubeSensor(CoordinatorEntity[LondonTubeCoordinator], SensorEntity):
    """Sensor that reads the status of a line from Tube Data."""

    _attr_attribution = "Powered by TfL Open Data"
    _attr_icon = "mdi:subway"
    _attr_has_entity_name = True  # Use modern entity naming
    _attr_device_info = DeviceInfo(
        identifiers={(DOMAIN, "tfl_tube")},
        name="London Underground",
        manufacturer="Transport for London",
        model="Tube Status",
        entry_type=DeviceEntryType.SERVICE,
    )

    def __init__(self, coordinator: LondonTubeCoordinator, name: str) -> None:
        """Initialize the London Underground sensor."""
        super().__init__(coordinator)
        self._name = name
        # Add unique_id for proper entity registry
        self._attr_unique_id = f"tube_{name.lower().replace(' ', '_')}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str:
        """Return the state of the sensor."""
        return self.coordinator.data[self.name]["State"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return other details about the sensor state."""
        return {"Description": self.coordinator.data[self.name]["Description"]}
