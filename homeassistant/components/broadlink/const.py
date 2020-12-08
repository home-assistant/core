"""Constants for the Broadlink integration."""
from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

DOMAIN = "broadlink"

DOMAINS_AND_TYPES = (
    (REMOTE_DOMAIN, ("RM2", "RM4")),
    (SENSOR_DOMAIN, ("A1", "RM2", "RM4")),
    (SWITCH_DOMAIN, ("MP1", "RM2", "RM4", "SP1", "SP2", "SP4", "SP4B")),
)

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5
