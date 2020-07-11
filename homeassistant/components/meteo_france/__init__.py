"""Support for Meteo-France weather data."""
import asyncio
import datetime
import logging

from meteofrance.client import meteofranceClient, meteofranceError
from vigilancemeteo import VigilanceMeteoError, VigilanceMeteoFranceProxy
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, HomeAssistantType
from homeassistant.util import Throttle

from .const import CONF_CITY, DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = datetime.timedelta(minutes=5)


CITY_SCHEMA = vol.Schema({vol.Required(CONF_CITY): cv.string})

CONFIG_SCHEMA = vol.Schema(
    {DOMAIN: vol.Schema(vol.All(cv.ensure_list, [CITY_SCHEMA]))}, extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistantType, config: ConfigType) -> bool:
    """Set up Meteo-France from legacy config file."""

    conf = config.get(DOMAIN)
    if conf is None:
        return True

    for city_conf in conf:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=city_conf.copy()
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry) -> bool:
    """Set up an Meteo-France account from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Weather alert
    weather_alert_client = VigilanceMeteoFranceProxy()
    try:
        await hass.async_add_executor_job(weather_alert_client.update_data)
    except VigilanceMeteoError as exp:
        _LOGGER.error(
            "Unexpected error when creating the vigilance_meteoFrance proxy: %s ", exp
        )
        return False
    hass.data[DOMAIN]["weather_alert_client"] = weather_alert_client

    # Weather
    city = entry.data[CONF_CITY]
    try:
        client = await hass.async_add_executor_job(meteofranceClient, city)
    except meteofranceError as exp:
        _LOGGER.error("Unexpected error when creating the meteofrance proxy: %s", exp)
        return False

    hass.data[DOMAIN][city] = MeteoFranceUpdater(client)
    await hass.async_add_executor_job(hass.data[DOMAIN][city].update)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )
    _LOGGER.debug("meteo_france sensor platform loaded for %s", city)
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
        hass.data[DOMAIN].pop(entry.data[CONF_CITY])

    return unload_ok


class MeteoFranceUpdater:
    """Update data from Meteo-France."""

    def __init__(self, client: meteofranceClient):
        """Initialize the data object."""
        self._client = client

    def get_data(self):
        """Get the latest data from Meteo-France."""
        return self._client.get_data()

    @Throttle(SCAN_INTERVAL)
    def update(self):
        """Get the latest data from Meteo-France."""

        try:
            self._client.update()
        except meteofranceError as exp:
            _LOGGER.error(
                "Unexpected error when updating the meteofrance proxy: %s", exp
            )
