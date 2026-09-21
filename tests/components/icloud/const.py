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

FIRST_NAME = "user"
LAST_NAME = "name"
USERNAME = "username@me.com"
USERNAME_2 = "second_username@icloud.com"
PASSWORD = "password"
PASSWORD_2 = "second_password"
WITH_FAMILY = True
MAX_INTERVAL = 15
GPS_ACCURACY_THRESHOLD = 250

MEMBER_1_FIRST_NAME = "John"
MEMBER_1_LAST_NAME = "TRAVOLTA"
MEMBER_1_FULL_NAME = MEMBER_1_FIRST_NAME + " " + MEMBER_1_LAST_NAME
MEMBER_1_PERSON_ID = (MEMBER_1_FIRST_NAME + MEMBER_1_LAST_NAME).lower()
MEMBER_1_APPLE_ID = MEMBER_1_PERSON_ID + "@icloud.com"

USER_INFO = {
    "accountFormatter": 0,
    "firstName": FIRST_NAME,
    "lastName": LAST_NAME,
    "membersInfo": {
        MEMBER_1_PERSON_ID: {
            "accountFormatter": 0,
            "firstName": MEMBER_1_FIRST_NAME,
            "lastName": MEMBER_1_LAST_NAME,
            "deviceFetchStatus": "DONE",
            "useAuthWidget": True,
            "isHSA": True,
            "appleId": MEMBER_1_APPLE_ID,
        }
    },
    "hasMembers": True,
}

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

LOCATION = {
    "latitude": 60.2,
    "longitude": 24.7,
    "horizontalAccuracy": 10,
}

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
    "location": LOCATION,
}

# iCloud reports no battery for a device that is asleep or has none of its
# own, such as a Mac mini, but still reports where it is.
DEVICE_WITHOUT_BATTERY = {
    "id": "device2",
    "name": "Mac mini",
    "deviceStatus": "200",
    "batteryStatus": "Unknown",
    "batteryLevel": None,
    "rawDeviceModel": "Macmini9,1",
    "deviceClass": "Mac",
    "deviceDisplayName": "Mac mini",
    "prsId": None,
    "lowPowerMode": False,
    "location": LOCATION,
}

# An account that is not sharing its location reports no location at all.
DEVICE_WITHOUT_LOCATION = {
    "id": "device3",
    "name": "iPad",
    "deviceStatus": "200",
    "batteryStatus": "NotCharging",
    "batteryLevel": 0.5,
    "rawDeviceModel": "iPad13,1",
    "deviceClass": "iPad",
    "deviceDisplayName": "iPad",
    "prsId": None,
    "lowPowerMode": False,
    "location": None,
}
