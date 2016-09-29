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
from homeassistant.helpers import config_per_platform
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.util import slugify

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

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): cv.string,
    vol.Optional(CONF_NAME): cv.string,
}, extra=vol.ALLOW_EXTRA)

NOTIFY_SERVICE_SCHEMA = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.template,
    vol.Optional(ATTR_TITLE): cv.template,
    vol.Optional(ATTR_TARGET): cv.string,
    vol.Optional(ATTR_DATA): dict,
})

_LOGGER = logging.getLogger(__name__)


def send_message(hass, message, title=None, data=None):
    """Send a notification message."""
    info = {
        ATTR_MESSAGE: message
    }

    if title is not None:
        info[ATTR_TITLE] = title

    if data is not None:
        info[ATTR_DATA] = data

    hass.services.call(DOMAIN, SERVICE_NOTIFY, info)


# pylint: disable=too-many-locals
def setup(hass, config):
    """Setup the notify services."""
    success = False

    descriptions = load_yaml_config_file(
        os.path.join(os.path.dirname(__file__), 'services.yaml'))

    targets = {}

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
            kwargs = {}
            message = call.data[ATTR_MESSAGE]
            title = call.data.get(ATTR_TITLE)

            if title:
                title.hass = hass
                kwargs[ATTR_TITLE] = title.render()

            if targets.get(call.service) is not None:
                kwargs[ATTR_TARGET] = targets[call.service]
            else:
                kwargs[ATTR_TARGET] = call.data.get(ATTR_TARGET)

            message.hass = hass
            kwargs[ATTR_MESSAGE] = message.render()
            kwargs[ATTR_DATA] = call.data.get(ATTR_DATA)

            notify_service.send_message(**kwargs)

        service_call_handler = partial(notify_message, notify_service)

        if hasattr(notify_service, 'targets'):
            platform_name = (p_config.get(CONF_NAME) or platform)
            for name, target in notify_service.targets.items():
                target_name = slugify("{}_{}".format(platform_name, name))
                targets[target_name] = target
                hass.services.register(DOMAIN, target_name,
                                       service_call_handler,
                                       descriptions.get(SERVICE_NOTIFY),
                                       schema=NOTIFY_SERVICE_SCHEMA)

        platform_name = (p_config.get(CONF_NAME) or SERVICE_NOTIFY)
        platform_name_slug = slugify(platform_name)

        hass.services.register(DOMAIN, platform_name_slug,
                               service_call_handler,
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
