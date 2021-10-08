"""The Environment Canada (EC) component."""
from functools import partial

from env_canada import ECData, ECRadar

from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE

from .const import CONF_LANGUAGE, CONF_STATION, DOMAIN

PLATFORMS = ["camera", "sensor", "weather"]


async def async_setup_entry(hass, config_entry):
    """Set up EC as config entry."""
    lat = config_entry.data.get(CONF_LATITUDE)
    lon = config_entry.data.get(CONF_LONGITUDE)
    station = config_entry.data.get(CONF_STATION)
    lang = config_entry.data.get(CONF_LANGUAGE, "English")

    coordinators = {}

    weather_init = partial(
        ECData, station_id=station, coordinates=(lat, lon), language=lang.lower()
    )
    weather_data = await hass.async_add_executor_job(weather_init)
    coordinators["weather_coordinator"] = weather_data

    radar_init = partial(ECRadar, coordinates=(lat, lon))
    radar_data = await hass.async_add_executor_job(radar_init)
    coordinators["radar_coordinator"] = radar_data
    await hass.async_add_executor_job(radar_data.get_loop)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinators

    hass.config_entries.async_setup_platforms(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok
