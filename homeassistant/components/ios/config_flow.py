"""Config flow for iOS."""
from homeassistant.helpers import config_entry_flow
from homeassistant import config_entries
from .const import DOMAIN


config_entry_flow.register_discovery_flow(
    DOMAIN, "Home Assistant iOS", lambda *_: True, config_entries.CONN_CLASS_CLOUD_PUSH
)
