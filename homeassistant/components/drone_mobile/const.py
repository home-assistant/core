"""Constants for the DroneMobile integration."""

DOMAIN = "drone_mobile"
VEHICLE = "DroneMobile Vehicle"
MANUFACTURER = "DroneMobile"

CONF_VEHICLE_ID = "vehicle_id"
CONF_UNIT = "units"
CONF_UNITS = ["imperial", "metric"]
CONF_UPDATE_INTERVAL = "update_interval"

DEFAULT_UNIT = "imperial"
DEFAULT_UPDATE_INTERVAL = 5

AVAILABLE_COMMANDS = {
    "device_status",
    "start",
    "stop",
    "lock",
    "unlock",
    "trunk",
    "panic_on",
    "panic_off",
    "aux1",
    "aux2",
    "location",
}

SENSORS = {
    "odometer": {"icon": "mdi:counter"},
    "battery": {"icon": "mdi:car-battery"},
    "temperature": {"icon": "mdi:thermometer"},
    "gps": {"icon": "mdi:radar"},
    "alarm": {"icon": "mdi:bell"},
    "ignitionStatus": {"icon": "hass:power"},
    "engineStatus": {"icon": "mdi:engine"},
    "doorStatus": {"icon": "mdi:car-door"},
    "trunkStatus": {"icon": "mdi:car-wash"},
    "hoodStatus": {"icon": "mdi:car-convertible"},
    "lastRefresh": {"icon": "mdi:clock"},
}

LOCKS = {
    "doorLock": {"icon": "mdi:car-door-lock"},
    "trunk": {"icon": "mdi:car-wash"},
}

SWITCHES = {
    "remoteStart": {"icon": "mdi:car-key"},
    "panic": {"icon": "mdi:access-point"},
    "aux1": {"icon": "mdi:numeric-1-box-multiple"},
    "aux2": {"icon": "mdi:numeric-2-box-multiple"},
}
