"""Constants."""

from homeassistant.const import Platform

DOMAIN = "broadlink"

DOMAINS_AND_TYPES = {
    Platform.CLIMATE: {"HYS"},
    Platform.REMOTE: {"RM4MINI", "RM4PRO", "RMMINI", "RMMINIB", "RMPRO"},
    Platform.SENSOR: {
        "A1",
        "MP1S",
        "RM4MINI",
        "RM4PRO",
        "RMPRO",
        "SP2S",
        "SP3S",
        "SP4",
        "SP4B",
    },
    Platform.SWITCH: {
        "BG1",
        "MP1",
        "MP1S",
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
    Platform.LIGHT: {"LB1", "LB2"},
}
DEVICE_TYPES = set.union(*DOMAINS_AND_TYPES.values())

DEFAULT_PORT = 80
DEFAULT_TIMEOUT = 5
