"""Constants for the Modem Caller ID integration."""
from typing import Final

from phone_modem import exceptions
from serial import SerialException

DATA_KEY_API = "api"
DEFAULT_NAME = "Phone Modem"
DOMAIN = "modem_callerid"
ICON = "mdi:phone-classic"

EXCEPTIONS: Final = (
    FileNotFoundError,
    exceptions.SerialError,
    exceptions.ResponseError,
    SerialException,
)


class CID:
    """CID Attributes."""

    CID_TIME = "cid_time"
    CID_NUMBER = "cid_number"
    CID_NAME = "cid_name"
