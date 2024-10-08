"""Constants for the Traccar Server integration."""

from logging import getLogger

DOMAIN = "traccar_server"
LOGGER = getLogger(__package__)

ATTR_ADDRESS = "address"
ATTR_ALTITUDE = "altitude"
ATTR_CATEGORY = "category"
ATTR_GEOFENCE = "geofence"
ATTR_MOTION = "motion"
ATTR_SPEED = "speed"
ATTR_STATUS = "status"
ATTR_TRACKER = "tracker"
ATTR_TRACCAR_ID = "traccar_id"

CONF_MAX_ACCURACY = "max_accuracy"
CONF_CUSTOM_ATTRIBUTES = "custom_attributes"
CONF_EVENTS = "events"
CONF_SKIP_ACCURACY_FILTER_FOR = "skip_accuracy_filter_for"

EVENTS = {
    "deviceMoving": "device_moving",
    "commandResult": "command_result",
    "deviceFuelDrop": "device_fuel_drop",
    "geofenceEnter": "geofence_enter",
    "deviceOffline": "device_offline",
    "driverChanged": "driver_changed",
    "geofenceExit": "geofence_exit",
    "deviceOverspeed": "device_overspeed",
    "deviceOnline": "device_online",
    "deviceStopped": "device_stopped",
    "maintenance": "maintenance",
    "alarm": "alarm",
    "textMessage": "text_message",
    "deviceUnknown": "device_unknown",
    "ignitionOff": "ignition_off",
    "ignitionOn": "ignition_on",
}
