"""Constants for the Alert integration."""

import logging
from typing import Final

DOMAIN: Final = "alert"

LOGGER = logging.getLogger(__package__)

CONF_CAN_ACK = "can_acknowledge"
CONF_NOTIFIERS = "notifiers"
CONF_SKIP_FIRST = "skip_first"
CONF_ALERT_MESSAGE = "message"
CONF_DONE_MESSAGE = "done_message"
CONF_TITLE = "title"
CONF_DATA = "data"

DEFAULT_CAN_ACK = True
DEFAULT_SKIP_FIRST = False
