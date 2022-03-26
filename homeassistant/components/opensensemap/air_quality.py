"""Support for openSenseMap Air Quality data."""
from __future__ import annotations

from datetime import timedelta
import logging

from opensensemap_api import OpenSenseMap
from opensensemap_api.exceptions import OpenSenseMapError
import voluptuous as vol

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by openSenseMap"

CONF_STATION_ID = "station_id"

SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the openSenseMap air quality platform."""

    name = config.get(CONF_NAME)
    station_id = config[CONF_STATION_ID]

    session = async_get_clientsession(hass)
    osm_api = OpenSenseMapData(OpenSenseMap(station_id, session))

    await osm_api.async_update()

    if "name" not in osm_api.api.data:
        _LOGGER.error("Station %s is not available", station_id)
        raise PlatformNotReady

    station_name = osm_api.api.data["name"] if name is None else name

    async_add_entities([OpenSenseMapQuality(station_name, osm_api)], True)


class OpenSenseMapQuality(AirQualityEntity):
    """Implementation of an openSenseMap air quality entity."""

    def __init__(self, name, osm):
        """Initialize the air quality entity."""
        self._name = name
        self._osm = osm

    @property
    def name(self):
        """Return the name of the air quality entity."""
        return self._name

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._osm.api.pm2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._osm.api.pm10

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    async def async_update(self):
        """Get the latest data from the openSenseMap API."""
        await self._osm.async_update()


class OpenSenseMapData:
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the latest data from the Pi-hole."""

        try:
            await self.api.get_data()
        except OpenSenseMapError as err:
            _LOGGER.error("Unable to fetch data: %s", err)
