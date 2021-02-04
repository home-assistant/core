"""Constants for the Vizio integration tests."""
from homeassistant.components.media_player import (
    DEVICE_CLASS_SPEAKER,
    DEVICE_CLASS_TV,
    DOMAIN as MP_DOMAIN,
)
from homeassistant.components.vizio.const import (
    CONF_ADDITIONAL_CONFIGS,
    CONF_APP_ID,
    CONF_APPS,
    CONF_APPS_TO_INCLUDE_OR_EXCLUDE,
    CONF_CONFIG,
    CONF_INCLUDE_OR_EXCLUDE,
    CONF_MESSAGE,
    CONF_NAME_SPACE,
    CONF_VOLUME_STEP,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_EXCLUDE,
    CONF_HOST,
    CONF_INCLUDE,
    CONF_NAME,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
)
from homeassistant.util import slugify

NAME = "Vizio"
NAME2 = "Vizio2"
HOST = "192.168.1.1:9000"
HOST2 = "192.168.1.2:9000"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2
UNIQUE_ID = "testid"
MODEL = "model"
VERSION = "version"

CH_TYPE = 1
RESPONSE_TOKEN = 1234
PIN = "abcd"


class MockStartPairingResponse:
    """Mock Vizio start pairing response."""

    def __init__(self, ch_type: int, token: int) -> None:
        """Initialize mock start pairing response."""
        self.ch_type = ch_type
        self.token = token


class MockCompletePairingResponse:
    """Mock Vizio complete pairing response."""

    def __init__(self, auth_token: str) -> None:
        """Initialize mock complete pairing response."""
        self.auth_token = auth_token


CURRENT_EQ = "Music"
EQ_LIST = ["Music", "Movie"]

CURRENT_INPUT = "HDMI"
INPUT_LIST = ["HDMI", "USB", "Bluetooth", "AUX"]

CURRENT_APP = "Hulu"
CURRENT_APP_CONFIG = {CONF_APP_ID: "3", CONF_NAME_SPACE: 4, CONF_MESSAGE: None}
APP_LIST = [
    {
        "name": "Hulu",
        "country": ["*"],
        "id": ["1"],
        "config": [{"NAME_SPACE": 4, "APP_ID": "3", "MESSAGE": None}],
    },
    {
        "name": "Netflix",
        "country": ["*"],
        "id": ["2"],
        "config": [{"NAME_SPACE": 1, "APP_ID": "2", "MESSAGE": None}],
    },
]
APP_NAME_LIST = [app["name"] for app in APP_LIST]
INPUT_LIST_WITH_APPS = INPUT_LIST + ["CAST"]
CUSTOM_CONFIG = {CONF_APP_ID: "test", CONF_MESSAGE: None, CONF_NAME_SPACE: 10}
ADDITIONAL_APP_CONFIG = {
    "name": CURRENT_APP,
    CONF_CONFIG: CUSTOM_CONFIG,
}
UNKNOWN_APP_CONFIG = {
    "APP_ID": "UNKNOWN",
    "NAME_SPACE": 10,
    "MESSAGE": None,
}

ENTITY_ID = f"{MP_DOMAIN}.{slugify(NAME)}"


MOCK_PIN_CONFIG = {CONF_PIN: PIN}

MOCK_USER_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

MOCK_OPTIONS = {
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_IMPORT_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_TV_WITH_INCLUDE_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_INCLUDE: [CURRENT_APP]},
}

MOCK_TV_WITH_EXCLUDE_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_EXCLUDE: ["Netflix"]},
}

MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_ADDITIONAL_CONFIGS: [ADDITIONAL_APP_CONFIG]},
}

MOCK_SPEAKER_APPS_FAILURE = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_ADDITIONAL_CONFIGS: [ADDITIONAL_APP_CONFIG]},
}

MOCK_TV_APPS_FAILURE = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: None,
}

MOCK_TV_APPS_WITH_VALID_APPS_CONFIG = {
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_APPS: {CONF_INCLUDE: [CURRENT_APP]},
}

MOCK_TV_CONFIG_NO_TOKEN = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
}

MOCK_SPEAKER_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SPEAKER,
}

MOCK_INCLUDE_APPS = {
    CONF_INCLUDE_OR_EXCLUDE: CONF_INCLUDE.title(),
    CONF_APPS_TO_INCLUDE_OR_EXCLUDE: [CURRENT_APP],
}

MOCK_INCLUDE_NO_APPS = {
    CONF_INCLUDE_OR_EXCLUDE: CONF_INCLUDE.title(),
    CONF_APPS_TO_INCLUDE_OR_EXCLUDE: [],
}

VIZIO_ZEROCONF_SERVICE_TYPE = "_viziocast._tcp.local."
ZEROCONF_NAME = f"{NAME}.{VIZIO_ZEROCONF_SERVICE_TYPE}"
ZEROCONF_HOST = HOST.split(":")[0]
ZEROCONF_PORT = HOST.split(":")[1]

MOCK_ZEROCONF_SERVICE_INFO = {
    CONF_TYPE: VIZIO_ZEROCONF_SERVICE_TYPE,
    CONF_NAME: ZEROCONF_NAME,
    CONF_HOST: ZEROCONF_HOST,
    CONF_PORT: ZEROCONF_PORT,
    "properties": {"name": "SB4031-D5"},
}
