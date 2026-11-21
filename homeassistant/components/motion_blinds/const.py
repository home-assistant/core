"""Constants for the Motionblinds component."""

from enum import StrEnum

from homeassistant.const import Platform

DOMAIN = "motion_blinds"
MANUFACTURER = "Motionblinds, Coulisse B.V."
DEFAULT_GATEWAY_NAME = "Motionblinds Gateway"

PLATFORMS = [Platform.BUTTON, Platform.COVER, Platform.SENSOR]

CONF_BLIND_TYPE_LIST = "blind_type_list"
CONF_WAIT_FOR_PUSH = "wait_for_push"
CONF_INTERFACE = "interface"
DEFAULT_WAIT_FOR_PUSH = False
DEFAULT_INTERFACE = "any"

KEY_GATEWAY = "gateway"
KEY_API_LOCK = "api_lock"

ATTR_WIDTH = "width"
ATTR_ABSOLUTE_POSITION = "absolute_position"
ATTR_AVAILABLE = "available"

UPDATE_INTERVAL = 600
UPDATE_INTERVAL_FAST = 60
UPDATE_DELAY_STOP = 3
UPDATE_DELAY_BLIND = 1.5
UPDATE_INTERVAL_MOVING = 5
UPDATE_INTERVAL_MOVING_WIFI = 45


class MotionBlindsService(StrEnum):
    """Store keys for Motionblinds services."""

    SET_ABSOLUTE_POSITION = "set_absolute_position"


class MotionBlindsServiceArgument(StrEnum):
    """Store keys for Motionblinds service arguments."""

    ABSOLUTE_POSITION = "absolute_position"
    TILT_POSITION = "tilt_position"
    WIDTH = "width"
