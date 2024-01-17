"""Constants for the Bluesound HiFi wireless speakers and audio integrations component."""


from homeassistant.const import Platform

DOMAIN = "bluesound"

PLATFORMS = [
    Platform.MEDIA_PLAYER,
]

SERVICE_CLEAR_TIMER = "clear_sleep_timer"
SERVICE_JOIN = "join"
SERVICE_SET_TIMER = "set_sleep_timer"
SERVICE_UNJOIN = "unjoin"

DEFAULT_PORT = 11000
