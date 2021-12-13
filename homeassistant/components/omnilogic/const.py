"""Constants for the Omnilogic integration."""

DOMAIN = "omnilogic"
CONF_SCAN_INTERVAL = "polling_interval"
DEFAULT_SCAN_INTERVAL = 6
DEFAULT_PH_OFFSET = 0
COORDINATOR = "coordinator"
OMNI_API = "omni_api"

PUMP_TYPES = {
    "FMT_VARIABLE_SPEED_PUMP": "VARIABLE",
    "FMT_SINGLE_SPEED": "SINGLE",
    "FMT_DUAL_SPEED": "DUAL",
    "PMP_VARIABLE_SPEED_PUMP": "VARIABLE",
    "PMP_SINGLE_SPEED": "SINGLE",
    "PMP_DUAL_SPEED": "DUAL",
}

ALL_ITEM_KINDS = {
    "BOWS",
    "Filter",
    "Heaters",
    "Chlorinator",
    "CSAD",
    "Lights",
    "Relays",
    "Pumps",
}
