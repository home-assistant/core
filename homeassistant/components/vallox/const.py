"""Constants for the Vallox integration."""

from datetime import timedelta

from vallox_websocket_api import Profile as VALLOX_PROFILE

DOMAIN = "vallox"
DEFAULT_NAME = "Vallox"

STATE_SCAN_INTERVAL = timedelta(seconds=60)

# Common metric keys and (default) values.
METRIC_KEY_MODE = "A_CYC_MODE"
METRIC_KEY_PROFILE_FAN_SPEED_HOME = "A_CYC_HOME_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_AWAY = "A_CYC_AWAY_SPEED_SETTING"
METRIC_KEY_PROFILE_FAN_SPEED_BOOST = "A_CYC_BOOST_SPEED_SETTING"

MODE_ON = 0
MODE_OFF = 5

DEFAULT_FAN_SPEED_HOME = 50
DEFAULT_FAN_SPEED_AWAY = 25
DEFAULT_FAN_SPEED_BOOST = 65

PRESET_MODE_TO_VALLOX_PROFILE = {
    "home": VALLOX_PROFILE.HOME,
    "away": VALLOX_PROFILE.AWAY,
    "boost": VALLOX_PROFILE.BOOST,
    "fireplace": VALLOX_PROFILE.FIREPLACE,
    "extra": VALLOX_PROFILE.EXTRA,
    "auto": VALLOX_PROFILE.AUTO,
}

VALLOX_PROFILE_TO_PRESET_MODE = {
    value: key for (key, value) in PRESET_MODE_TO_VALLOX_PROFILE.items()
}

VALLOX_CELL_STATE_TO_STR = {
    0: "heat_recovery",
    1: "cool_recovery",
    2: "bypass",
    3: "defrosting",
}

# The vallox_websocket_api client uses a hardcoded value of 65535 to
# represent an indefinite duration.
PROFILE_DURATION_INDEFINITE = 65535
