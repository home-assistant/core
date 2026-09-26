"""Support for Automation Device Specification (ADS)."""

from enum import StrEnum

DOMAIN = "ads"

DEFAULT_PORT = 851

CONF_ADS_VAR = "adsvar"
CONF_LOCAL_NET_ID = "local_net_id"

STATE_KEY_STATE = "state"


class AdsType(StrEnum):
    """Supported Types."""

    BOOL = "bool"
    BYTE = "byte"
    INT = "int"
    UINT = "uint"
    SINT = "sint"
    USINT = "usint"
    DINT = "dint"
    UDINT = "udint"
    WORD = "word"
    DWORD = "dword"
    LREAL = "lreal"
    REAL = "real"
    STRING = "string"
    TIME = "time"
    DATE = "date"
    DATE_AND_TIME = "dt"
    TOD = "tod"
