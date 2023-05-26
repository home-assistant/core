"""Constants for the Owlet Smart Sock integration."""

DOMAIN = "owlet"

CONF_OWLET_EXPIRY = "expiry"
CONF_OWLET_REFRESH = "refresh"

SUPPORTED_VERSIONS = [3]
POLLING_INTERVAL = 5
MANUFACTURER = "Owlet Baby Care"
SLEEP_STATES = {0: "Unknown", 1: "Awake", 8: "Light Sleep", 15: "Deep Sleep"}
