"""Constants for the ENOcean integration."""
import logging

DOMAIN = "enocean"
DATA_ENOCEAN = "enocean"

ERROR_INVALID_DONGLE_PATH = "invalid_dongle_path"

SIGNAL_RECEIVE_MESSAGE = "enocean.receive_message"
SIGNAL_SEND_MESSAGE = "enocean.send_message"

LOGGER = logging.getLogger(__package__)
