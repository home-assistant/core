"""
Provides functionality to notify people.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/notify/
"""
from functools import partial
import logging
import os

import voluptuous as vol

import homeassistant.bootstrap as bootstrap
from homeassistant.config import load_yaml_config_file
from homeassistant.helpers import config_per_platform, template
from homeassistant.helpers.config_validation import PLATFORM_SCHEMA  # noqa
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME

DOMAIN = "notify"

# Title of notification
ATTR_TITLE = "title"
ATTR_TITLE_DEFAULT = "Home Assistant"

# Target of the notification (user, device, etc)
ATTR_TARGET = 'target'

# Text to notify user of
ATTR_MESSAGE = "message"

# Platform specific data
ATTR_DATA = 'data'

SERVICE_NOTIFY = "notify"

NOTIFY_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.string,
    vol.Optional(ATTR_TARGET): cv.string,
    vol.Optional(ATTR_DATA): dict,      # nobody seems to be using this (yet)
})

_LOGGER = logging.getLogger(__name__)


def send_message(hass, message, title=None):
    """Send a notification message."""
    data = {
        ATTR_MESSAGE: message
    }

    if title is not None:
        data[ATTR_TITLE] = title

    hass.services.call(DOMAIN, SERVICE_NOTIFY, data)


def setup(hass, config):
    """Setup the notify services."""
    success = False

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    for platform, p_config in config_per_platform(config, DOMAIN):
        notify_implementation = bootstrap.prepare_setup_platform(
            hass, config, DOMAIN, platform)

        if notify_implementation is None:
            _LOGGER.error("Unknown notification service specified.")
            continue

        notify_service = notify_implementation.get_service(hass, p_config)

        if notify_service is None:
            _LOGGER.error("Failed to initialize notification service %s",
                          platform)
            continue

        def notify_message(notify_service, call):
            """Handle sending notification message service calls."""
            message = call.data[ATTR_MESSAGE]

            title = template.render(
                hass, call.data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT))
            target = call.data.get(ATTR_TARGET)
            message = template.render(hass, message)
            data = call.data.get(ATTR_DATA)

            notify_service.send_message(message, title=title, target=target,
                                        data=data)

        service_call_handler = partial(notify_message, notify_service)
        service_notify = p_config.get(CONF_NAME, SERVICE_NOTIFY)
        hass.services.register(DOMAIN, service_notify, service_call_handler,
                               descriptions.get(SERVICE_NOTIFY),
                               schema=NOTIFY_SERVICE_SCHEMA)
        success = True

    return success


# pylint: disable=too-few-public-methods
class BaseNotificationService(object):
    """An abstract class for notification services."""

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError
