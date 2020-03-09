"""iCloud component constants."""

DOMAIN = "icloud"
SERVICE_UPDATE = f"{DOMAIN}_update"

CONF_MAX_INTERVAL = "max_interval"
CONF_GPS_ACCURACY_THRESHOLD = "gps_accuracy_threshold"

DEFAULT_MAX_INTERVAL = 30  # min
DEFAULT_GPS_ACCURACY_THRESHOLD = 500  # meters

# to store the cookie
STORAGE_KEY = DOMAIN
STORAGE_VERSION = 1

PLATFORMS = ["device_tracker", "sensor"]

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
