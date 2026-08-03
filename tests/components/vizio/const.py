"""Constants for the Vizio integration tests."""

from ipaddress import ip_address

from vizaio import AppConfig, AppRecord, PairChallenge, SettingInfo, SettingType
from vizaio.profiles import SOUNDBAR_PROFILE, TV_PROFILE

from homeassistant.components.media_player import (
    DOMAIN as MP_DOMAIN,
    MediaPlayerDeviceClass,
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
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
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

PIN = "abcd"

PAIR_CHALLENGE = PairChallenge(challenge_type=1, token=1234)

MAX_VOLUME = {
    MediaPlayerDeviceClass.TV: TV_PROFILE.max_volume,
    MediaPlayerDeviceClass.SPEAKER: SOUNDBAR_PROFILE.max_volume,
}


def audio_setting(
    name: str, value: int | str, options: tuple[str, ...] = ()
) -> SettingInfo:
    """Build an audio SettingInfo for mock device responses."""
    return SettingInfo(
        setting_type="audio",
        name=name,
        value=value,
        hashval=0,
        type=SettingType.SLIDER if isinstance(value, int) else SettingType.LIST,
        options=options,
    )


CURRENT_EQ = "Music"
EQ_LIST = ["Music", "Movie"]

CURRENT_INPUT = "HDMI"
INPUT_LIST = ["HDMI", "USB", "Bluetooth", "AUX"]

CURRENT_APP = "Hulu"
CURRENT_APP_CONFIG = {CONF_APP_ID: "3", CONF_NAME_SPACE: 4, CONF_MESSAGE: None}
CURRENT_APP_CONFIG_OBJ = AppConfig(app_id="3", name_space=4, message=None)
APP_RECORDS = (
    AppRecord(
        name="Hulu",
        country=("*",),
        config=(AppConfig(app_id="3", name_space=4, message=None),),
        id="1",
    ),
    AppRecord(
        name="Netflix",
        country=("*",),
        config=(AppConfig(app_id="2", name_space=1, message=None),),
        id="2",
    ),
)
APP_NAME_LIST = [app.name for app in APP_RECORDS]
INPUT_LIST_WITH_APPS = [*INPUT_LIST, "CAST"]
CUSTOM_CONFIG = {CONF_APP_ID: "test", CONF_MESSAGE: None, CONF_NAME_SPACE: 10}
CUSTOM_CONFIG_OBJ = AppConfig(app_id="test", name_space=10, message=None)
ADDITIONAL_APP_CONFIG = {
    "name": CURRENT_APP,
    CONF_CONFIG: CUSTOM_CONFIG,
}
UNKNOWN_APP_CONFIG = {
    "APP_ID": "UNKNOWN",
    "NAME_SPACE": 10,
    "MESSAGE": None,
}
UNKNOWN_APP_CONFIG_OBJ = AppConfig(app_id="UNKNOWN", name_space=10, message=None)

ENTITY_ID = f"{MP_DOMAIN}.{slugify(NAME)}"


MOCK_PIN_CONFIG = {CONF_PIN: PIN}

MOCK_USER_VALID_TV_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
}

MOCK_OPTIONS = {
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_TV_WITH_INCLUDE_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_INCLUDE: [CURRENT_APP]},
}

MOCK_TV_WITH_EXCLUDE_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_EXCLUDE: ["Netflix"]},
}

MOCK_TV_WITH_ADDITIONAL_APPS_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
    CONF_APPS: {CONF_ADDITIONAL_CONFIGS: [ADDITIONAL_APP_CONFIG]},
}


MOCK_TV_APPS_WITH_VALID_APPS_CONFIG = {
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_APPS: {CONF_INCLUDE: [CURRENT_APP]},
}

MOCK_TV_CONFIG_NO_TOKEN = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.TV,
}

MOCK_SPEAKER_CONFIG = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: MediaPlayerDeviceClass.SPEAKER,
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
ZEROCONF_HOST, ZEROCONF_PORT = HOST.split(":", maxsplit=2)

MOCK_ZEROCONF_SERVICE_INFO = ZeroconfServiceInfo(
    ip_address=ip_address(ZEROCONF_HOST),
    ip_addresses=[ip_address(ZEROCONF_HOST)],
    hostname="mock_hostname",
    name=ZEROCONF_NAME,
    port=ZEROCONF_PORT,
    properties={"name": "SB4031-D5"},
    type=VIZIO_ZEROCONF_SERVICE_TYPE,
)
