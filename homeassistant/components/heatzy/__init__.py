"""Heatzy platform configuration."""
import logging

from heatzypy import HeatzyClient
from heatzypy.exception import HeatzyException, HttpRequestFailed

from homeassistant.components.climate.const import DOMAIN as CLIM_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.exceptions import ConfigEntryNotReady

from .const import DOMAIN, HEATZY_API, HEATZY_DEVICES

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, config_entry):
    """Set up Heatzy as config entry."""
    try:
        await async_connect_heatzy(hass, config_entry.data)
    except HeatzyException as error:
        raise ConfigEntryNotReady from error

    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(config_entry, CLIM_DOMAIN)
    )
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, [CLIM_DOMAIN]
    )
    return unload_ok


async def async_connect_heatzy(hass, data):
    """Connect to heatzy."""
    try:
        api = HeatzyClient(data[CONF_USERNAME], data[CONF_PASSWORD])
        devices = await hass.async_add_executor_job(api.get_devices)
        if devices is not None:
            hass.data[DOMAIN] = {HEATZY_API: api, HEATZY_DEVICES: devices}
    except (HttpRequestFailed, HeatzyException) as error:
        _LOGGER.error(error)
        raise HeatzyException from error
