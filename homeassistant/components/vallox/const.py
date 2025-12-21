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

I18N_KEY_TO_VALLOX_PROFILE = {
    "home": VALLOX_PROFILE.HOME,
    "away": VALLOX_PROFILE.AWAY,
    "boost": VALLOX_PROFILE.BOOST,
    "fireplace": VALLOX_PROFILE.FIREPLACE,
    "extra": VALLOX_PROFILE.EXTRA,
}

VALLOX_PROFILE_TO_PRESET_MODE = {
    VALLOX_PROFILE.HOME: "Home",
    VALLOX_PROFILE.AWAY: "Away",
    VALLOX_PROFILE.BOOST: "Boost",
    VALLOX_PROFILE.FIREPLACE: "Fireplace",
    VALLOX_PROFILE.EXTRA: "Extra",
}

PRESET_MODE_TO_VALLOX_PROFILE = {
    value: key for (key, value) in VALLOX_PROFILE_TO_PRESET_MODE.items()
}

VALLOX_CELL_STATE_TO_STR = {
    0: "Heat Recovery",
    1: "Cool Recovery",
    2: "Bypass",
    3: "Defrosting",
}
