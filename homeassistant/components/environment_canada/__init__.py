"""The Environment Canada (EC) component."""
from functools import partial
import logging

from env_canada import ECData, ECRadar

from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import CONF_LANGUAGE, CONF_STATION, DOMAIN

PLATFORMS = ["camera", "sensor", "weather"]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up EC as config entry."""
    lat = config_entry.data.get(CONF_LATITUDE)
    lon = config_entry.data.get(CONF_LONGITUDE)
    station = config_entry.data.get(CONF_STATION)
    lang = config_entry.data.get(CONF_LANGUAGE, "English")

    weather_api = {}

    weather_init = partial(
        ECData, station_id=station, coordinates=(lat, lon), language=lang.lower()
    )
    weather_data = await hass.async_add_executor_job(weather_init)
    weather_api["weather_data"] = weather_data

    radar_init = partial(ECRadar, coordinates=(lat, lon))
    radar_data = await hass.async_add_executor_job(radar_init)
    weather_api["radar_data"] = radar_data
    await hass.async_add_executor_job(radar_data.get_loop)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = weather_api

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


def trigger_import(hass, config):
    """Trigger a import of YAML config into a config_entry."""
    _LOGGER.warning(
        "Environment Canada YAML configuration is deprecated; your YAML configuration "
        "has been imported into the UI and can be safely removed"
    )
    if not config.get(CONF_LANGUAGE):
        config[CONF_LANGUAGE] = "English"

    data = {}
    for key in (
        CONF_STATION,
        CONF_LATITUDE,
        CONF_LONGITUDE,
        CONF_LANGUAGE,
    ):  # pylint: disable=consider-using-tuple
        if config.get(key):
            data[key] = config[key]

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=data
        )
    )
