"""Config flow for Cast."""
import functools

from pychromecast.discovery import discover_chromecasts, stop_discovery

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN
from .helpers import ChromeCastZeroconf


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""

    casts, browser = await hass.async_add_executor_job(
        functools.partial(
            discover_chromecasts, zeroconf_instance=ChromeCastZeroconf.get_zeroconf()
        )
    )
    stop_discovery(browser)
    return casts


config_entry_flow.register_discovery_flow(
    DOMAIN, "Google Cast", _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH
)
