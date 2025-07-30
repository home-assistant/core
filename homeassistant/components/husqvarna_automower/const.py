"""The constants for the Husqvarna Automower integration."""

from aioautomower.model import MowerStates

DOMAIN = "husqvarna_automower"
EXECUTION_TIME_DELAY = 5
NAME = "Husqvarna Automower"
OAUTH2_AUTHORIZE = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/authorize"
OAUTH2_TOKEN = "https://api.authentication.husqvarnagroup.dev/v1/oauth2/token"

ERROR_STATES = [
    MowerStates.ERROR_AT_POWER_UP,
    MowerStates.ERROR,
    MowerStates.FATAL_ERROR,
    MowerStates.OFF,
    MowerStates.STOPPED,
    MowerStates.WAIT_POWER_UP,
    MowerStates.WAIT_UPDATING,
]
