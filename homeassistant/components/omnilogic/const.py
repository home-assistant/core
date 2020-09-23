"""Constants for the Omnilogic integration."""

DOMAIN = "omnilogic"
CONF_SCAN_INTERVAL = "polling_interval"
COORDINATOR = "coordinator"
OMNI_API = "omni_api"
ATTR_IDENTIFIERS = "identifiers"
ATTR_MANUFACTURER = "manufacturer"
ATTR_MODEL = "model"

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
    "Heater",
    "Chlorinator",
    "CSAD",
    "Lights",
    "Relays",
    "Pumps",
}
