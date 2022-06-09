"""Config flow for iOS."""
from homeassistant.helpers import config_entry_flow

from .const import DOMAIN

config_entry_flow.register_discovery_flow(
    DOMAIN, "Home Assistant iOS", lambda hass: True
)
