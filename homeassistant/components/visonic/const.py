"""Constants for the connection to a Visonic PowerMax or PowerMaster Alarm System."""

import logging
import re
from typing import Final

from homeassistant.const import Platform

# The client version and domain information for the integration
DOMAIN: Final = "visonic"
CLIENT_VERSION: Final = "1.0.0.0"
MANUFACTURER: Final = "Visonic"
VISONIC_UNIQUE_NAME: Final = "Visonic Security System"
VISONIC_ALARM: Final = "Visonic Alarm"
VISONIC_PANEL: Final = "Visonic Panel"
VISONIC_TRANSLATION_KEY: Final = "alarm_panel_key"

LOGGER = logging.getLogger(__package__)

PANEL_ATTRIBUTE_NAME: Final = "panel"

# Default connection details (connection can be one of Ethernet, Serial, RS232)
DEFAULT_DEVICE_HOST: Final = "127.0.0.1"
DEFAULT_DEVICE_PORT: Final = 30000
DEFAULT_DEVICE_SERIAL: Final = "/dev/ttyUSB0"
DEFAULT_DEVICE_BAUD: Final = 9600
DEFAULT_PANEL_USER_CODE: Final = "1111"
DEFAULT_CLOUD_SCAN_INTERVAL: Final = 20
DEFAULT_DIRECT_SCAN_INTERVAL: Final = 60

# Text strings for entity attributes
TEXT_DISCONNECTION_COUNT: Final = "Disconnection Count"
TEXT_CLIENT_VERSION: Final = "Client Version"

# These are the strings for the various abort and error indications to the user for the configuration
CONFIG_INVALID_DEVICE_TYPE: Final = "device_error"
CONFIG_SETTINGS_MISSING: Final = "settings_missing"
CONFIG_EMAIL_INVALID: Final = "email_invalid"
CONFIG_CONNECTION_TIMEOUT: Final = "cannot_connect_timeout"
CONFIG_CONNECTION_REFUSED: Final = "cannot_connect_refused"
CONFIG_SETTINGS_INVALID: Final = "settings_invalid"
CONFIG_PANEL_NOT_REGISTERED: Final = "panel_not_registered"
CONFIG_PANEL_MISMATCH: Final = "panel_mismatch"
CONFIG_PANEL_NUMBER_IN_USE: Final = "panel_number_in_use"
CONFIG_CLOUD_ERROR: Final = "cloud_error"
CONFIG_NO_CLOUD_PANELS: Final = "no_panels"
CONFIG_INVALID_AUTH_OR_PIN: Final = "invalid_auth"
CONFIG_FLOW_ALREADY_CONFIGURED: Final = "already_configured"
CONFIG_FLOW_ALREADY_IN_PROGRESS: Final = "already_in_progress"

# Translation exceptions throughout the integration, maintained here to ensure consistency in language translation
TRANSLATE_EXCEPTION_DISARM_CODE_NOT_ENTERED: Final = "invalid_disarm_state_code"
TRANSLATE_EXCEPTION_INITIAL_CONNECTION_FAILURE: Final = (
    "panel_initial_connection_failure"
)
TRANSLATE_EXCEPTION_AUTHORISATION_FAILURE: Final = "panel_authorisation_failure"

# These are the control flow names for the config variables.
# settings that are used for creation
CONF_DOWNLOAD_CODE: Final = "download_code"
CONF_PANEL_NUMBER: Final = "panel_number"
CONF_USER_CODE_SLOT: Final = "user_code_slot"
CONF_CLOUD_APP_ID: Final = "cloud_app_id"
CONF_PANEL_SERIAL: Final = "panel_serial"

# settings than can be modified
CONF_ARM_CODE_AUTO: Final = "arm_without_usercode"
CONF_ARM_HOME_ENABLED: Final = "arm_home_enabled"
CONF_ENABLE_REMOTE_ARM: Final = "allow_remote_arm"
CONF_ENABLE_REMOTE_DISARM: Final = "allow_remote_disarm"
CONF_EPROM_ATTRIBUTES: Final = "show_eeprom_attributes"  # leave as eeprom as this will change the config params in HA
CONF_INSTANT_ARM_AWAY: Final = "arm_away_instant"
CONF_INSTANT_ARM_HOME: Final = "arm_home_instant"
CONF_RETRY_CONNECTION_COUNT: Final = "retry_connection_count"
CONF_RETRY_CONNECTION_DELAY: Final = "retry_connection_delay"

# The baud rate for serial connections is managed internally and not set by the user
# For a new connection, the default (9600) is used, the working baud is saved to entry.data
# If the baud is set in entry.data then it is tried first
CONF_DEVICE_BAUD: Final = "baud"

TEXT_PANEL_MODEL = "panel_model"

PIN_REGEX: Final = re.compile(r"^[0-9]{4}$")

PLATFORMS: Final = [
    Platform.ALARM_CONTROL_PANEL,
    #    Platform.BINARY_SENSOR,
    #    Platform.BUTTON,
    #    Platform.IMAGE,
    #    Platform.SELECT,
    #    Platform.SENSOR,
    #    Platform.SIREN,
    #    Platform.SWITCH,
]

# What notifications to send to the HA Frontend
MAX_CLIENT_LOG_ENTRIES: Final = 1000

# The main configuration forms
#   These need to be in the language translation file
FORM_DEVICE: Final = "device"
FORM_DEVICE_NO_PANEL: Final = "device_no_panel"
FORM_ETHERNET: Final = "form_ethernet"
FORM_SERIAL: Final = "form_serial"
FORM_CLOUD: Final = "form_cloud"
FORM_POWERLINK: Final = "form_powerlink"
FORM_CONNECTION: Final = "parameters_connection"
FORM_PANEL_ARMING: Final = "parameters_panel_arming"
FORM_SELECT_PANEL: Final = "select_panel"
