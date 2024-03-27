"""Sensor for checking the status of London Underground tube lines."""

from __future__ import annotations

import logging
from typing import Any

from london_tube_status import TubeData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_LINE, TUBE_LINES
from .coordinator import LondonTubeCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
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


class LondonTubeSensor(CoordinatorEntity[LondonTubeCoordinator], SensorEntity):
    """Sensor that reads the status of a line from Tube Data."""

    _attr_attribution = "Powered by TfL Open Data"
    _attr_icon = "mdi:subway"

    def __init__(self, coordinator: LondonTubeCoordinator, name: str) -> None:
        """Initialize the London Underground sensor."""
        super().__init__(coordinator)
        self._name = name

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
