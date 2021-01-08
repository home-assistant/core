"""Config flow for TP-Link."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from .const import DOMAIN
from .common import async_get_discoverable_devices


config_entry_flow.register_discovery_flow(
    DOMAIN,
    "TP-Link Smart Home",
    async_get_discoverable_devices,
    config_entries.CONN_CLASS_LOCAL_POLL,
)
