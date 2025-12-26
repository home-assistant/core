"""iCloud component constants."""

from homeassistant.const import Platform
from homeassistant.generated.entity_platforms import EntityPlatforms

DOMAIN = "icloud"

ATTRIBUTION = "Data provided by Apple iCloud"

CONF_WITH_FAMILY = "with_family"
CONF_MAX_INTERVAL = "max_interval"
CONF_GPS_ACCURACY_THRESHOLD = "gps_accuracy_threshold"

CONF_ALBUM_ID = "album_id"
CONF_ALBUM_NAME = "album_name"
CONF_ALBUM_TYPE = "album_type"
CONF_RANDOM_ORDER = "album_random_order"
CONF_PICTURE_INTERVAL = "album_picture_interval"

DEFAULT_WITH_FAMILY: bool = False
DEFAULT_MAX_INTERVAL = 30  # min
DEFAULT_GPS_ACCURACY_THRESHOLD = 500  # meters

DEFAULT_RANDOM_ORDER: bool = False
DEFAULT_PICTURE_INTERVAL: float = 30.0  # seconds

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 2

PLATFORMS: list[EntityPlatforms] = [
    Platform.CAMERA,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]

# pyicloud.AppleDevice status
DEVICE_BATTERY_LEVEL = "batteryLevel"
DEVICE_BATTERY_STATUS = "batteryStatus"
DEVICE_CLASS = "deviceClass"
DEVICE_DISPLAY_NAME = "deviceDisplayName"
DEVICE_ID = "id"
DEVICE_LOCATION = "location"
DEVICE_LOCATION_HORIZONTAL_ACCURACY = "horizontalAccuracy"
DEVICE_LOCATION_LATITUDE = "latitude"
DEVICE_LOCATION_LONGITUDE = "longitude"
DEVICE_LOST_MODE_CAPABLE = "lostModeCapable"
DEVICE_LOW_POWER_MODE = "lowPowerMode"
DEVICE_NAME = "name"
DEVICE_PERSON_ID = "prsId"
DEVICE_RAW_DEVICE_MODEL = "rawDeviceModel"
DEVICE_STATUS = "deviceStatus"

DEVICE_STATUS_SET = [
    "features",
    "maxMsgChar",
    "darkWake",
    "fmlyShare",
    DEVICE_STATUS,
    "remoteLock",
    "activationLocked",
    DEVICE_CLASS,
    DEVICE_ID,
    "deviceModel",
    DEVICE_RAW_DEVICE_MODEL,
    "passcodeLength",
    "canWipeAfterLock",
    "trackingInfo",
    DEVICE_LOCATION,
    "msg",
    DEVICE_BATTERY_LEVEL,
    "remoteWipe",
    "thisDevice",
    "snd",
    DEVICE_PERSON_ID,
    "wipeInProgress",
    DEVICE_LOW_POWER_MODE,
    "lostModeEnabled",
    "isLocating",
    DEVICE_LOST_MODE_CAPABLE,
    "mesg",
    DEVICE_NAME,
    DEVICE_BATTERY_STATUS,
    "lockedTimestamp",
    "lostTimestamp",
    "locationCapable",
    DEVICE_DISPLAY_NAME,
    "lostDevice",
    "deviceColor",
    "wipedTimestamp",
    "modelDisplayName",
    "locationEnabled",
    "isMac",
    "locFoundEnabled",
]

DEVICE_STATUS_CODES = {
    "200": "online",
    "201": "offline",
    "203": "pending",
    "204": "unregistered",
}


# entity / service attributes
ATTR_ACCOUNT = "account"
ATTR_ACCOUNT_FETCH_INTERVAL = "account_fetch_interval"
ATTR_BATTERY = "battery"
ATTR_BATTERY_STATUS = "battery_status"
ATTR_DEVICE_NAME = "device_name"
ATTR_DEVICE_STATUS = "device_status"
ATTR_LOW_POWER_MODE = "low_power_mode"
ATTR_LOST_DEVICE_MESSAGE = "message"
ATTR_LOST_DEVICE_NUMBER = "number"
ATTR_LOST_DEVICE_SOUND = "sound"
ATTR_OWNER_NAME = "owner_fullname"
