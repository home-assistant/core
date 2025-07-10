"""Lutron Caseta constants."""

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
DEVICE_TYPE_COLOR_TUNE = "ColorTune"

MANUFACTURER = "Lutron Electronics Co., Inc"

ATTR_SERIAL = "serial"
ATTR_TYPE = "type"
ATTR_BUTTON_TYPE = "button_type"
ATTR_LEAP_BUTTON_NUMBER = "leap_button_number"
ATTR_BUTTON_NUMBER = "button_number"  # LIP button number
ATTR_DEVICE_NAME = "device_name"
ATTR_AREA_NAME = "area_name"
ATTR_ACTION = "action"

ACTION_PRESS = "press"
ACTION_RELEASE = "release"

CONF_SUBTYPE = "subtype"

CONNECT_TIMEOUT = 9
CONFIGURE_TIMEOUT = 50

UNASSIGNED_AREA = "Unassigned"

CONFIG_URL = "https://device-login.lutron.com"
