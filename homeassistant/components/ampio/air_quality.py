"""Support for Ampio Air Quality data."""
from datetime import timedelta
import logging

from asmog import AmpioSmog
import voluptuous as vol

from homeassistant.components.air_quality import PLATFORM_SCHEMA, AirQualityEntity
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Data provided by Ampio"
CONF_STATION_ID = "station_id"
SCAN_INTERVAL = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_STATION_ID): cv.string, vol.Optional(CONF_NAME): cv.string}
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Ampio Smog air quality platform."""

    name = config.get(CONF_NAME)
    station_id = config[CONF_STATION_ID]

    session = async_get_clientsession(hass)
    api = AmpioSmogMapData(AmpioSmog(station_id, hass.loop, session))

    await api.async_update()

    if not api.api.data:
        _LOGGER.error("Station %s is not available", station_id)
        return

    async_add_entities([AmpioSmogQuality(api, station_id, name)], True)


class AmpioSmogQuality(AirQualityEntity):
    """Implementation of an Ampio Smog air quality entity."""

    def __init__(self, api, station_id, name):
        """Initialize the air quality entity."""
        self._ampio = api
        self._station_id = station_id
        self._name = name or api.api.name

    @property
    def name(self):
        """Return the name of the air quality entity."""
        return self._name

    @property
    def unique_id(self):
        """Return unique_name."""
        return f"ampio_smog_{self._station_id}"

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._ampio.api.pm2_5

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._ampio.api.pm10

    @property
    def attribution(self):
        """Return the attribution."""
        return ATTRIBUTION

    async def async_update(self):
        """Get the latest data from the AmpioMap API."""
        await self._ampio.async_update()


class AmpioSmogMapData:
    """Get the latest data and update the states."""

    def __init__(self, api):
        """Initialize the data object."""
        self.api = api

    @Throttle(SCAN_INTERVAL)
    async def async_update(self):
        """Get the latest data from AmpioMap."""
        await self.api.get_data()
