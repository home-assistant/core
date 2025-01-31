"""The NMBS component."""

import logging

from pyrail import iRail

from homeassistant.components.sensor import DOMAIN as DOMAIN_SENSOR
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PLATFORM, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, NMBS_KEY, NMBSGlobalData, gather_localized_station_names

_LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR]

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the NMBS component."""

    api_client = iRail()

    hass.data.setdefault(DOMAIN, {})
    station_response = await hass.async_add_executor_job(api_client.get_stations)
    if station_response == -1:
        return False
    hass.data[NMBS_KEY] = NMBSGlobalData()
    hass.data[NMBS_KEY].stations = station_response["station"]

    if DOMAIN_SENSOR in config:
        has_nmbs = False
        for sensor_config in config[DOMAIN_SENSOR]:
            if sensor_config[CONF_PLATFORM] == DOMAIN:
                has_nmbs = True
        if has_nmbs:
            hass.data[NMBS_KEY].localized_names = await gather_localized_station_names(
                hass
            )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up NMBS from a config entry."""

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
