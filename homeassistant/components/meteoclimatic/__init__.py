"""Support for Meteoclimatic weather data."""
import asyncio
import datetime
import logging

from meteoclimatic.exceptions import MeteoclimaticError
from meteoclimatic import MeteoclimaticClient
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

from .const import CONF_STATION_CODE, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


STATION_CODE_SCHEMA = vol.Schema({vol.Required(CONF_STATION_CODE): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [STATION_CODE_SCHEMA]))},
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up Meteoclimatic from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for station_code_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=station_code_conf.copy()
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an Meteoclimatic account from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Weather
    station_code = entry.data[CONF_STATION_CODE]
    client = MeteoclimaticClient()
    hass.data[DOMAIN][station_code] = MeteoclimaticUpdater(client, station_code)
    await hass.async_add_executor_job(hass.data[DOMAIN][station_code].update)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    _LOGGER.debug("meteoclimatic sensor platform loaded for %s", station_code)
    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.data[CONF_STATION_CODE])

    return unload_ok


class MeteoclimaticUpdater:
    """Update data from Meteclimatic weather service."""

    def __init__(self, client: MeteoclimaticClient, station_code: str):
        """Initialize the data object."""
        self._data = None
        self._client = client
        self._station_code = station_code

    def get_data(self):
        """Return the latest data from Meteoclimatic."""
        return self._data

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Obtain the latest data from Meteoclimatic."""

        try:
            self._data = self._client.weather_at_station(self._station_code)
        except MeteoclimaticError as exp:
            _LOGGER.error(
                "Unexpected error when obtaining data from Meteoclimatic: %s", exp
            )
