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

# Fakers
FIRST_NAME = "user"
LAST_NAME = "name"

MEMBER_1_FIRST_NAME = "John"
MEMBER_1_LAST_NAME = "TRAVOLTA"
MEMBER_1_FULL_NAME = MEMBER_1_FIRST_NAME + " " + MEMBER_1_LAST_NAME
MEMBER_1_PERSON_ID = (MEMBER_1_FIRST_NAME + MEMBER_1_LAST_NAME).lower()
MEMBER_1_APPLE_ID = MEMBER_1_PERSON_ID + "@icloud.com"

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

DEVICE = {
    "id": "device1",
    "name": "iPhone",
    "deviceStatus": "200",
    "batteryStatus": "NotCharging",
    "batteryLevel": 0.8,
    "rawDeviceModel": "iPhone14,2",
    "deviceClass": "iPhone",
    "deviceDisplayName": "iPhone",
    "prsId": None,
    "lowPowerMode": False,
    "location": None,
}
