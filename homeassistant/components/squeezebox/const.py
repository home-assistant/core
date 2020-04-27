"""Constants for the Squeezebox component."""
from homeassistant.const import STATE_IDLE, STATE_PAUSED, STATE_PLAYING

DOMAIN = "squeezebox"
SERVICE_CALL_METHOD = "call_method"
SQUEEZEBOX_MODE = {
    "pause": STATE_PAUSED,
    "play": STATE_PLAYING,
    "stop": STATE_IDLE,
}
