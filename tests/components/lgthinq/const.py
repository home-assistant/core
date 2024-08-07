"""Constants for lgthinq test."""

from typing import Final

from homeassistant.components.lgthinq.const import LIVE_TV_APP_ID
from homeassistant.components.media_player import DOMAIN as MP_DOMAIN

# A list of device type strings.
AIR_CONDITIONER: Final[str] = "DEVICE_AIR_CONDITIONER"
AIR_PURIFIER_FAN: Final[str] = "DEVICE_AIR_PURIFIER_FAN"
AIR_PURIFIER: Final[str] = "DEVICE_AIR_PURIFIER"
CEILING_FAN: Final[str] = "DEVICE_CEILING_FAN"
COOKTOP: Final[str] = "DEVICE_COOKTOP"
DEHUMIDIFIER: Final[str] = "DEVICE_DEHUMIDIFIER"
DISH_WASHER: Final[str] = "DEVICE_DISH_WASHER"
DRYER: Final[str] = "DEVICE_DRYER"
HOOD: Final[str] = "DEVICE_HOOD"
HOME_BREW: Final[str] = "DEVICE_HOME_BREW"
HUMIDIFIER: Final[str] = "DEVICE_HUMIDIFIER"
KIMCHI_REFRIGERATOR: Final[str] = "DEVICE_KIMCHI_REFRIGERATOR"
MICROWAVE_OVEN: Final[str] = "DEVICE_MICROWAVE_OVEN"
OVEN: Final[str] = "DEVICE_OVEN"
PLANT_CULTIVATOR: Final[str] = "DEVICE_PLANT_CULTIVATOR"
REFRIGERATOR: Final[str] = "DEVICE_REFRIGERATOR"
ROBOT_CLEANER: Final[str] = "DEVICE_ROBOT_CLEANER"
SYSTEM_BOILER: Final[str] = "DEVICE_SYSTEM_BOILER"
STICK_CLEANER: Final[str] = "DEVICE_STICK_CLEANER"
STYLER: Final[str] = "DEVICE_STYLER"
WASHER: Final[str] = "DEVICE_WASHER"
WASHCOMBO_MAIN: Final[str] = "DEVICE_WASHCOMBO_MAIN"
WASHCOMBO_MINI: Final[str] = "DEVICE_WASHCOMBO_MINI"
WASHTOWER_DRYER: Final[str] = "DEVICE_WASHTOWER_DRYER"
WASHTOWER_WASHER: Final[str] = "DEVICE_WASHTOWER_WASHER"
WASHTOWER: Final[str] = "DEVICE_WASHTOWER"
WATER_HEATER: Final[str] = "DEVICE_WATER_HEATER"
WATER_PURIFIER: Final[str] = "DEVICE_WATER_PURIFIER"
WINE_CELLAR: Final[str] = "DEVICE_WINE_CELLAR"

# Common constants for testing.
FAKE_UUID: Final[str] = "some-fake-uuid"
SOURCE_THINQ = "thinq"
SOURCE_REGION = "region"

# For testing thinq appliance.
THINQ_TEST_PAT: Final[str] = (
    "123abc4567de8f90g123h4ij56klmn789012p345rst6uvw789xy"
)
THINQ_TEST_NAME: Final[str] = "Test ThinQ"
THINQ_TEST_COUNTRY: Final[str] = "KR"

# For testing webos TV.
WEBOSTV_HOST: Final[str] = "192.168.1.1"
WEBOSTV_NAME: Final[str] = "fake_webos"
WEBOSTV_ENTITY_ID: Final[str] = f"{MP_DOMAIN}.{WEBOSTV_NAME}"
WEBOSTV_CLIENT_KEY: Final[str] = "some-secret"

WEBOSTV_CHANNEL_1: Final[dict] = {
    "channelNumber": "1",
    "channelName": "Channel 1",
    "channelId": "ch1id",
}
WEBOSTV_CHANNEL_2: Final[dict] = {
    "channelNumber": "20",
    "channelName": "Channel Name 2",
    "channelId": "ch2id",
}
WEBOSTV_MOCK_APPS: Final[dict] = {
    LIVE_TV_APP_ID: {
        "title": "Live TV",
        "id": LIVE_TV_APP_ID,
        "largeIcon": "large-icon",
        "icon": "icon",
    },
}
WEBOSTV_MOCK_INPUTS: Final[dict] = {
    "in1": {"label": "Input01", "id": "in1", "appId": "app0"},
    "in2": {"label": "Input02", "id": "in2", "appId": "app1"},
}

WEBOSTV_MULTI_SELECT_SOURCES: Final[list] = ["Input01", "Input02", "Live TV"]
