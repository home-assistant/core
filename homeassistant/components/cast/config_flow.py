"""Config flow for Cast."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from .const import DOMAIN


async def _async_has_devices(hass):
    """Return if there are devices that can be discovered."""
    from pychromecast.discovery import discover_chromecasts

    return await hass.async_add_executor_job(discover_chromecasts)


config_entry_flow.register_discovery_flow(
    DOMAIN, "Google Cast", _async_has_devices, config_entries.CONN_CLASS_LOCAL_PUSH
)
