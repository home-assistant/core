"""The buienradar integration."""
import asyncio
import logging

import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

from .const import (
    CONF_CAMERA,
    CONF_COUNTRY,
    CONF_DELTA,
    CONF_SENSOR,
    CONF_TIMEFRAME,
    CONF_WEATHER,
    DEFAULT_COUNTRY,
    DEFAULT_DELTA,
    DEFAULT_TIMEFRAME,
    DOMAIN,
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

PLATFORMS = [CONF_WEATHER, CONF_CAMERA, CONF_SENSOR]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the buienradar component."""
    hass.data.setdefault(DOMAIN, {})

    weather_configs = _filter_domain_configs(config, "weather", DOMAIN)
    sensor_configs = _filter_domain_configs(config, "sensor", DOMAIN)
    camera_configs = _filter_domain_configs(config, "camera", DOMAIN)

    _import_weather_configs(hass, weather_configs, sensor_configs, camera_configs)

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up buienradar from a config entry."""
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )

    return unload_ok


def _import_weather_configs(hass, weather_configs, sensor_configs, camera_configs):
    camera_config = {}
    if len(camera_configs) > 0:
        camera_config = camera_configs[0]

    for config in sensor_configs:
        # Remove weather configurations which share lat/lon with sensor configurations
        matching_weather_config = None
        latitude = config.get(CONF_LATITUDE, hass.config.latitude)
        longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
        for weather_config in weather_configs:
            weather_latitude = config.get(CONF_LATITUDE, hass.config.latitude)
            weather_longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
            if latitude == weather_latitude and longitude == weather_longitude:
                matching_weather_config = weather_config
                break

        if matching_weather_config is not None:
            weather_configs.remove(matching_weather_config)

    configs = weather_configs + sensor_configs

    for config in configs:
        _LOGGER.debug("Importing Buienradar %s", config)

        data = {
            CONF_LATITUDE: config.get(CONF_LATITUDE, hass.config.latitude),
            CONF_LONGITUDE: config.get(CONF_LONGITUDE, hass.config.longitude),
            CONF_TIMEFRAME: config.get(CONF_TIMEFRAME, DEFAULT_TIMEFRAME),
            CONF_COUNTRY: camera_config.get(CONF_COUNTRY, DEFAULT_COUNTRY),
            CONF_DELTA: camera_config.get(CONF_DELTA, DEFAULT_DELTA),
        }

        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_IMPORT},
                data=data,
            )
        )


def _filter_domain_configs(config, domain, platform):
    configs = []
    for entry in config:
        if entry.startswith(domain):
            configs = configs + list(
                filter(lambda elem: elem["platform"] == platform, config[entry])
            )
    return configs
