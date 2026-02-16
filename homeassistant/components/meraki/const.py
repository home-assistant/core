"""Constants for the Meraki integration."""

DOMAIN = "meraki"

CONF_VALIDATOR = "validator"
CONF_SECRET = "secret"

URL = "/api/meraki"
ACCEPTED_VERSIONS = ["2.0", "2.1"]

__all__ = [
    "ACCEPTED_VERSIONS",
    "CONF_SECRET",
    "CONF_VALIDATOR",
    "DOMAIN",
    "URL",
]
