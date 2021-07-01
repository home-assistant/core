"""Config flow for Wemo."""

import pywemo

from homeassistant.helpers import config_entry_flow

from . import DOMAIN


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    return bool(await hass.async_add_executor_job(pywemo.discover_devices))


config_entry_flow.register_discovery_flow(DOMAIN, "Wemo", _async_has_devices)
