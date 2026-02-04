"""Constants for the Helios integration."""

from datetime import timedelta

from helios_websocket_api import Profile as HELIOS_PROFILE

DOMAIN = "helios"
DEFAULT_NAME = "Helios"

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

I18N_KEY_TO_HELIOS_PROFILE = {
    "home": HELIOS_PROFILE.HOME,
    "away": HELIOS_PROFILE.AWAY,
    "boost": HELIOS_PROFILE.BOOST,
    "fireplace": HELIOS_PROFILE.FIREPLACE,
    "extra": HELIOS_PROFILE.EXTRA,
}

HELIOS_PROFILE_TO_PRESET_MODE = {
    HELIOS_PROFILE.HOME: "Home",
    HELIOS_PROFILE.AWAY: "Away",
    HELIOS_PROFILE.BOOST: "Boost",
    HELIOS_PROFILE.FIREPLACE: "Fireplace",
    HELIOS_PROFILE.EXTRA: "Extra",
}

PRESET_MODE_TO_HELIOS_PROFILE = {
    value: key for (key, value) in HELIOS_PROFILE_TO_PRESET_MODE.items()
}

HELIOS_CELL_STATE_TO_STR = {
    0: "Heat Recovery",
    1: "Cool Recovery",
    2: "Bypass",
    3: "Defrosting",
}
