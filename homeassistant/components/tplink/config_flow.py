"""Config flow for TP-Link."""
from homeassistant.helpers import config_entry_flow

from .common import async_get_discoverable_devices
from .const import DOMAIN

config_entry_flow.register_discovery_flow(
    DOMAIN,
    "TP-Link Smart Home",
    async_get_discoverable_devices,
)
