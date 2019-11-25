"""Config flow for UPNP."""
from homeassistant import config_entries
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN
from .device import Device

config_entry_flow.register_discovery_flow(
    DOMAIN, "UPnP/IGD", Device.async_discover, config_entries.CONN_CLASS_LOCAL_POLL
)
