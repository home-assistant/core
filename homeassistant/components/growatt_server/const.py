"""Define constants for the Growatt Server component."""
CONF_PLANT_ID = "plant_id"

DEFAULT_PLANT_ID = "0"

DEFAULT_NAME = "Growatt"

SERVER_URLS = [
    "https://server.growatt.com/",
    "https://server-us.growatt.com/",
    "http://server.smten.com/",
]

DEFAULT_URL = SERVER_URLS[0]

DOMAIN = "growatt_server"

PLATFORMS = ["sensor"]

LOGIN_INVALID_AUTH_CODE = "502"
