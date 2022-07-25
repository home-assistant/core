"""Sensor for checking the status of London Underground tube lines."""
from __future__ import annotations

from datetime import timedelta
import logging

import async_timeout
from london_tube_status import TubeData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

_LOGGER = logging.getLogger(__name__)

DOMAIN = "london_underground"

ATTRIBUTION = "Powered by TfL Open Data"

CONF_LINE = "line"

ICON = "mdi:subway"

SCAN_INTERVAL = timedelta(seconds=30)

TUBE_LINES = [
    "Bakerloo",
    "Central",
    "Circle",
    "District",
    "DLR",
    "Hammersmith & City",
    "Jubilee",
    "London Overground",
    "Metropolitan",
    "Northern",
    "Piccadilly",
    "TfL Rail",
    "Victoria",
    "Waterloo & City",
]

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

    sensors = []
    for line in config[CONF_LINE]:
        sensors.append(LondonTubeSensor(coordinator, line))

    async_add_entities(sensors)


class LondonTubeCoordinator(DataUpdateCoordinator):
    """London Underground sensor coordinator."""

    def __init__(self, hass, data):
        """Initialize coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self._data = data

    async def _async_update_data(self):
        async with async_timeout.timeout(10):
            await self._data.update()
            return self._data.data


class LondonTubeSensor(CoordinatorEntity[LondonTubeCoordinator], SensorEntity):
    """Sensor that reads the status of a line from Tube Data."""

    def __init__(self, coordinator, name):
        """Initialize the London Underground sensor."""
        super().__init__(coordinator)
        self._name = name
        self.attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self.coordinator.data[self.name]["State"]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return other details about the sensor state."""
        self.attrs["Description"] = self.coordinator.data[self.name]["Description"]
        return self.attrs
