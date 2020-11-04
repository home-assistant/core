"""Constants for the Broadlink integration."""
import broadlink as blk

from homeassistant.components.remote import DOMAIN as REMOTE_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN

DOMAIN = "broadlink"

LIBRARY_URL = "https://github.com/mjg59/python-broadlink"

DOMAINS_AND_TYPES = {
    REMOTE_DOMAIN: {"RM4MINI", "RM4PRO", "RMMINI", "RMMINIB", "RMPRO"},
    SENSOR_DOMAIN: {"A1", "RM4MINI", "RM4PRO", "RMPRO"},
    SWITCH_DOMAIN: {
        "BG1",
        "MP1",
        "RM4MINI",
        "RM4PRO",
        "RMMINI",
        "RMMINIB",
        "RMPRO",
        "SP1",
        "SP2",
        "SP2S",
        "SP3",
        "SP3S",
        "SP4",
        "SP4B",
    },
}

TYPES_AND_CLASSES = {
    "A1": blk.a1,
    "BG1": blk.bg1,
    "MP1": blk.mp1,
    "RM4MINI": blk.rm4mini,
    "RM4PRO": blk.rm4pro,
    "RMMINI": blk.rmmini,
    "RMMINIB": blk.rmminib,
    "RMPRO": blk.rmpro,
    "SP1": blk.sp1,
    "SP2": blk.sp2,
    "SP2S": blk.sp2s,
    "SP3": blk.sp3,
    "SP3S": blk.sp3s,
    "SP4": blk.sp4,
    "SP4B": blk.sp4b,
}

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5
