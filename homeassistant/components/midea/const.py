"""Constants for the Midea integration."""

from enum import IntEnum
import logging

_LOGGER = logging.getLogger(__package__)

DOMAIN = "midea"


CONF_KEY = "key"
CONF_SUBTYPE = "subtype"
CONF_ACCOUNT = "account"
CONF_SERVER = "server"


class FanSpeed(IntEnum):
    """FanSpeed reference values."""

    LOW = 20
    MEDIUM = 40
    HIGH = 60
    FULL_SPEED = 80
    AUTO = 100
