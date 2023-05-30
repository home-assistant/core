"""Constants for the Owlet Smart Sock integration."""

DOMAIN = "owlet"

CONF_OWLET_EXPIRY = "expiry"
CONF_OWLET_REFRESH = "refresh"

SUPPORTED_VERSIONS = [3]
POLLING_INTERVAL = 5
MANUFACTURER = "Owlet Baby Care"
SLEEP_STATES = {0: "unknown", 1: "awake", 8: "light_sleep", 15: "deep_sleep"}
