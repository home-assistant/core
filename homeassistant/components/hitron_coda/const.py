"""Constants for the Hitron CODA integration."""

from datetime import timedelta

DOMAIN = "hitron_coda"
DEFAULT_TYPE = "rogers"
ROUTER_TYPES = ("rogers", "shaw")
UPDATE_INTERVAL = timedelta(seconds=12)
