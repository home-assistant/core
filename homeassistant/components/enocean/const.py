"""Constants for the EnOcean integration."""

import logging

from homeassistant.const import Platform

DOMAIN = "enocean"
DATA_ENOCEAN = "enocean"

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"


# config
CONF_ENOCEAN_DEVICES = "devices"
CONF_ENOCEAN_DEVICE_ID = "id"
CONF_ENOCEAN_DEVICE_NAME = "name"
CONF_ENOCEAN_MANAGE_DEVICE_COMMANDS = "manage_device_command"
CONF_ENOCEAN_DEVICE_TYPE_ID = "device_type_id"
CONF_ENOCEAN_SENDER_ID = "sender_id"

# step ids
ENOCEAN_STEP_ID_INIT = "init"
ENOCEAN_STEP_ID_ADD_DEVICE = "add_device"
ENOCEAN_STEP_ID_EDIT_DEVICE = "edit_device"
ENOCEAN_STEP_ID_DELETE_DEVICE = "delete_device"
ENOCEAN_STEP_ID_SELECT_DEVICE = "select_device_to_edit"

# menu options
ENOCEAN_MENU_OPTION_ADD_DEVICE = "add_device"
ENOCEAN_MENU_OPTION_DELETE_DEVICE = "delete_device"
ENOCEAN_MENU_OPTION_SELECT_DEVICE = "select_device_to_edit"

# errors
ENOCEAN_ERROR_DEVICE_ALREADY_CONFIGURED = "device_already_configured"
ENOCEAN_ERROR_DEVICE_NAME_EMPTY = "device_name_empty"
ENOCEAN_ERROR_INVALID_DEVICE_ID = "invalid_device_id"
ENOCEAN_ERROR_INVALID_SENDER_ID = "invalid_sender_id"

# others
ENOCEAN_DEFAULT_DEVICE_ID = "00:00:00:00"
ENOCEAN_DEFAULT_DEVICE_NAME = "EnOcean device"
ENOCEAN_DEVICE_TYPE_ID = "device_type_id"


LOGGER = logging.getLogger(__package__)

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.COVER,
    Platform.EVENT,
    Platform.LIGHT,
    Platform.SENSOR,
    Platform.SWITCH,
]


ENOCEAN_BINARY_SENSOR_EEPS = [
    "F6-02-01",  # Rocker Switch 1BS
    "F6-02-02",  # Rocker Switch 2BS
]
