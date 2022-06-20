"""Sensor for checking the status of London Underground tube lines."""
from __future__ import annotations

from datetime import timedelta

from london_tube_status import TubeData
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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
    await data.update()

    sensors = []
    for line in config[CONF_LINE]:
        sensors.append(LondonTubeSensor(line, data))

    async_add_entities(sensors, True)


class LondonTubeSensor(SensorEntity):
    """Sensor that reads the status of a line from Tube Data."""

    def __init__(self, name, data):
        """Initialize the London Underground sensor."""
        self._data = data
        self._description = None
        self._name = name
        self._state = None
        self.attrs = {ATTR_ATTRIBUTION: ATTRIBUTION}

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    @property
    def extra_state_attributes(self):
        """Return other details about the sensor state."""
        self.attrs["Description"] = self._description
        return self.attrs

    async def async_update(self):
        """Update the sensor."""
        await self._data.update()
        self._state = self._data.data[self.name]["State"]
        self._description = self._data.data[self.name]["Description"]
