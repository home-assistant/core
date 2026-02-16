"""Constants for the Meraki integration."""

from homeassistant.const import CONF_SECRET

DOMAIN = "meraki"

CONF_VALIDATOR = "validator"

URL = "/api/meraki"
ACCEPTED_VERSIONS = ["2.0", "2.1"]

__all__ = [
    "ACCEPTED_VERSIONS",
    "CONF_SECRET",
    "CONF_VALIDATOR",
    "DOMAIN",
    "URL",
]
