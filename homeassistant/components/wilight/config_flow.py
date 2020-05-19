"""Config flow for WiLight."""
import pywilight

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    devices = await hass.async_add_executor_job(pywilight.discover_devices)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN,
    "WiLight",
    _async_has_devices,
    config_entries.CONN_CLASS_LOCAL_PUSH,
    # config_entries.CONN_CLASS_UNKNOWN,
)
