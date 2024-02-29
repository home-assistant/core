"""Constants for the Plexamp Media Player integration."""

from homeassistant.components.media_player import RepeatMode

DOMAIN = "plexamp"

# constants for optional configuration entries
CONF_PLEX_TOKEN = "plex_token"
CONF_PLEX_IP_ADDRESS = "plex_ip_address"


# media player configurations
POLL_WAIT = 0
POLL_INCLUDE_METADA = 1
POLL_COMMAND_ID = 1

REPEAT_MODE_TO_NUMBER = {
    RepeatMode.ALL: "2",
    RepeatMode.ONE: "1",
    RepeatMode.OFF: "0",
}
NUMBER_TO_REPEAT_MODE = {
    "0": RepeatMode.OFF,
    "1": RepeatMode.ONE,
    "2": RepeatMode.ALL,
}
