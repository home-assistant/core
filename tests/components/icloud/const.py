"""Constants for the iCloud tests."""
from homeassistant.components.icloud.const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DEFAULT_GPS_ACCURACY_THRESHOLD,
    DEFAULT_MAX_INTERVAL,
    DEFAULT_WITH_FAMILY,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME

USERNAME = "username@me.com"
USERNAME_2 = "second_username@icloud.com"
PASSWORD = "password"
PASSWORD_2 = "second_password"
WITH_FAMILY = True
MAX_INTERVAL = 15
GPS_ACCURACY_THRESHOLD = 250

MOCK_CONFIG = {
    CONF_USERNAME: USERNAME,
    CONF_PASSWORD: PASSWORD,
    CONF_WITH_FAMILY: DEFAULT_WITH_FAMILY,
    CONF_MAX_INTERVAL: DEFAULT_MAX_INTERVAL,
    CONF_GPS_ACCURACY_THRESHOLD: DEFAULT_GPS_ACCURACY_THRESHOLD,
}

TRUSTED_DEVICES = [
    {"deviceType": "SMS", "areaCode": "", "phoneNumber": "*******58", "deviceId": "1"}
]
