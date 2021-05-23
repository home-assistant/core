"""Config flow for TP-Link."""
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_flow

from .common import async_get_discoverable_devices
from .const import DOMAIN


async def _async_has_devices(hass: HomeAssistant) -> bool:
    """Check if there are devices that can be discovered."""
    devices = await async_get_discoverable_devices(hass)
    return len(devices) > 0


config_entry_flow.register_discovery_flow(
    DOMAIN,
    "TP-Link Smart Home",
    _async_has_devices,
)
