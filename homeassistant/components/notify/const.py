"""Provide common notify constants."""

import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

ATTR_DATA = "data"

# Text to notify user of
ATTR_MESSAGE = "message"

# Target of the (legacy) notification (user, device, etc)
ATTR_TARGET = "target"

# Recipients for a notification
ATTR_RECIPIENTS = "recipients"

# Title of notification
ATTR_TITLE = "title"

DOMAIN = "notify"

LOGGER = logging.getLogger(__package__)

SERVICE_NOTIFY = "notify"
SERVICE_SEND_MESSAGE = "send_message"
SERVICE_PERSISTENT_NOTIFICATION = "persistent_notification"

NOTIFY_SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_MESSAGE): cv.template,
        vol.Optional(ATTR_TITLE): cv.template,
        vol.Optional(ATTR_TARGET): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(ATTR_DATA): dict,
    }
)
