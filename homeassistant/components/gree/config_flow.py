"""Config flow for Gree."""
from greeclimate.discovery import Discovery

from homeassistant.helpers import config_entry_flow

from .const import DISCOVERY_TIMEOUT, DOMAIN


async def _async_has_devices(hass) -> bool:
    """Return if there are devices that can be discovered."""
    gree_discovery = Discovery(DISCOVERY_TIMEOUT)
    devices = await gree_discovery.scan(wait_for=DISCOVERY_TIMEOUT)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(DOMAIN, "Gree Climate", _async_has_devices)
