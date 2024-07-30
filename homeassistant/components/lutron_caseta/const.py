"""Lutron Caseta constants."""

from typing import Final

DOMAIN = "lutron_caseta"

CONF_KEYFILE = "keyfile"
CONF_CERTFILE = "certfile"
CONF_CA_CERTS = "ca_certs"

STEP_IMPORT_FAILED = "import_failed"
ERROR_CANNOT_CONNECT = "cannot_connect"
ABORT_REASON_CANNOT_CONNECT = "cannot_connect"

LUTRON_CASETA_BUTTON_EVENT = "lutron_caseta_button_event"

BRIDGE_DEVICE_ID = "1"

DEVICE_TYPE_WHITE_TUNE = "WhiteTune"
DEVICE_TYPE_SPECTRUM_TUNE = "SpectrumTune"

MANUFACTURER = "Lutron Electronics Co., Inc"

ATTR_SERIAL: Final = "serial"
ATTR_TYPE: Final = "type"
ATTR_BUTTON_TYPE: Final = "button_type"
ATTR_LEAP_BUTTON_NUMBER: Final = "leap_button_number"
ATTR_BUTTON_NUMBER: Final = "button_number"  # LIP button number
ATTR_DEVICE_NAME: Final = "device_name"
ATTR_AREA_NAME: Final = "area_name"
ATTR_ACTION: Final = "action"

ACTION_PRESS = "press"
ACTION_RELEASE = "release"

CONF_SUBTYPE = "subtype"

BRIDGE_TIMEOUT = 35

UNASSIGNED_AREA = "Unassigned"

CONFIG_URL = "https://device-login.lutron.com"
