"""Provide common notify constants."""

import logging
from typing import Final

import probatio

from homeassistant.helpers import config_validation as cv

ATTR_DATA = "data"

# Text to notify user of
ATTR_MESSAGE = "message"

# Target of the (legacy) notification (user, device, etc)
ATTR_TARGET = "target"

# Recipients for a notification
ATTR_RECIPIENTS = "recipients"

# Title of notification
ATTR_TITLE = "title"

DOMAIN: Final = "notify"

LOGGER = logging.getLogger(__package__)

SERVICE_NOTIFY = "notify"
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_PERSISTENT_NOTIFICATION = "persistent_notification"

NOTIFY_SERVICE_SCHEMA = probatio.Schema(
    {
        probatio.Required(ATTR_MESSAGE): cv.string,
        probatio.Optional(ATTR_TITLE): cv.string,
        probatio.Optional(ATTR_TARGET): probatio.All(cv.ensure_list, [cv.string]),
        probatio.Optional(ATTR_DATA): dict,
    }
)
