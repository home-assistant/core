"""Config flow for Gree."""
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .bridge import DeviceHelper
from .const import DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    devices = await DeviceHelper.find_devices()
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Gree Climate", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
