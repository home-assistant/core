"""Config flow for Gree."""
from greeclimate.discovery import Discovery

from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DISCOVERY_TIMEOUT, DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    gree_discovery = Discovery(DISCOVERY_TIMEOUT)
    devices, _ = await gree_discovery.search_devices()
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN, "Gree Climate", _async_has_devices, config_entries.CONN_CLASS_LOCAL_POLL
)
