"""Constants for the Modem Caller ID integration."""
from typing import Final

from phone_modem import exceptions
from serial import SerialException

DATA_KEY_API = "api"
DATA_KEY_COORDINATOR = "coordinator"
DEFAULT_DEVICE = "/dev/ttyACM0"
DEFAULT_NAME = "Phone Modem"
DOMAIN = "modem_callerid"
ICON = "mdi:phone-classic"
STATE_CALLERID = "callerid"
STATE_RING = "ring"
SERVICE_REJECT_CALL = "reject_call"

EXCEPTIONS: Final = FileNotFoundError, exceptions.SerialError, SerialException


class CID:
    """CID Attributes."""

    CID_TIME = "cid_time"
    CID_NUMBER = "cid_number"
    CID_NAME = "cid_name"
