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
import homeassistant.helpers.config_validation as cv
from homeassistant.const import CONF_NAME, CONF_PLATFORM
from homeassistant.util import slugify

DOMAIN = "notify"
GROUP_DOMAIN = "notifygroup"

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
    vol.Optional(ATTR_TITLE, default=ATTR_TITLE_DEFAULT): cv.string,
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
            message = call.data[ATTR_MESSAGE]

            title = template.render(
                hass, call.data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT))
            if targets.get(call.service) is not None:
                target = targets[call.service]['target']
            else:
                target = call.data.get(ATTR_TARGET)
            message = template.render(hass, message)
            data = call.data.get(ATTR_DATA)

            notify_service.send_message(message, title=title, target=target,
                                        data=data)

        service_call_handler = partial(notify_message, notify_service)
        platform_name = (p_config.get(CONF_NAME) or SERVICE_NOTIFY)
        platform_name_slug = slugify(platform_name)

        if hasattr(notify_service, 'get_targets'):
            for name in notify_service.get_targets().keys():
                target_name = slugify("{}_{}".format(platform_name_slug,
                                                     name))
                targets[target_name] = {"platform": platform_name,
                                        "target": name}
                hass.services.register(DOMAIN, target_name,
                                       service_call_handler,
                                       descriptions.get(SERVICE_NOTIFY),
                                       schema=NOTIFY_SERVICE_SCHEMA)

        hass.services.register(DOMAIN, platform_name_slug,
                               service_call_handler,
                               descriptions.get(SERVICE_NOTIFY),
                               schema=NOTIFY_SERVICE_SCHEMA)
        success = True

    def notify_group(group, call):
        """Notify a group of targets."""
        for target in group:
            hass.services.call(DOMAIN, target, call.data)

    if config.get('notifygroups') is not None:
        for group_name, group in config.get('notifygroups').items():
            hass.services.register(GROUP_DOMAIN, slugify(group_name),
                                   partial(notify_group, group),
                                   descriptions.get(SERVICE_NOTIFY),
                                   schema=NOTIFY_SERVICE_SCHEMA)

    return success


# pylint: disable=too-few-public-methods
class BaseNotificationService(object):
    """An abstract class for notification services."""

    def send_message(self, message, **kwargs):
        """Send a message.

        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError
