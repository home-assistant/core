"""Constants for the BSB-Lan integration."""
from typing import Final

DOMAIN = "bsblan"

DATA_BSBLAN_CLIENT: Final = "bsblan_client"
DATA_BSBLAN_TIMER: Final = "bsblan_timer"
DATA_BSBLAN_UPDATED: Final = "bsblan_updated"

ATTR_TARGET_TEMPERATURE: Final = "target_temperature"
ATTR_INSIDE_TEMPERATURE: Final = "inside_temperature"
ATTR_OUTSIDE_TEMPERATURE: Final = "outside_temperature"

ATTR_STATE_ON: Final = "on"
ATTR_STATE_OFF: Final = "off"

CONF_DEVICE_IDENT: Final = "device_identification"
CONF_CONTROLLER_FAM: Final = "controller_family"
CONF_CONTROLLER_VARI: Final = "controller_variant"

SENSOR_TYPE_TEMPERATURE: Final = "temperature"

CONF_PASSKEY: Final = "passkey"
