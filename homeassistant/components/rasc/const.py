"""Constants for the rasc integration."""
import logging

DOMAIN = "rasc"

RASC_ACK = "ack"
RASC_START = "start"
RASC_COMPLETE = "complete"
RASC_RESPONSE = "rasc_response"
RASC_SCHEDULED = "scheduled"

CONF_TRANSITION = "transition"
DEFAULT_FAILURE_TIMEOUT = 30  # s
CHANGE_TIMEOUT = 5
ACTION_LENGTH_PADDING = 1.0  # second
MIN_RESCHEDULE_TIME = 1.0  # second
ACK_TO_START = 0.4  # second

LOGGER = logging.getLogger(__package__)
