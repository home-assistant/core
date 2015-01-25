"""
homeassistant.components.notify
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Provides functionality to notify people.
"""
import logging

from homeassistant.loader import get_component
from homeassistant.helpers import validate_config

from homeassistant.const import CONF_PLATFORM

DOMAIN = "notify"
DEPENDENCIES = []

# Title of notification
ATTR_TITLE = "title"
ATTR_TITLE_DEFAULT = "Home Assistant"

# Text to notify user of
ATTR_MESSAGE = "message"

SERVICE_NOTIFY = "notify"

_LOGGER = logging.getLogger(__name__)


def send_message(hass, message):
    """ Send a notification message. """
    hass.services.call(DOMAIN, SERVICE_NOTIFY, {ATTR_MESSAGE: message})


def setup(hass, config):
    """ Sets up notify services. """

    if not validate_config(config, {DOMAIN: [CONF_PLATFORM]}, _LOGGER):
        return False

    platform = config[DOMAIN].get(CONF_PLATFORM)

    notify_implementation = get_component(
        'notify.{}'.format(platform))

    if notify_implementation is None:
        _LOGGER.error("Unknown notification service specified.")

        return False

    notify_service = notify_implementation.get_service(hass, config)

    if notify_service is None:
        _LOGGER.error("Failed to initialize notification service %s",
                      platform)

        return False

    def notify_message(call):
        """ Handle sending notification message service calls. """
        message = call.data.get(ATTR_MESSAGE)

        if message is None:
            return

        title = call.data.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)

        notify_service.send_message(message, title=title)

    hass.services.register(DOMAIN, SERVICE_NOTIFY, notify_message)

    return True


# pylint: disable=too-few-public-methods
class BaseNotificationService(object):
    """ Provides an ABC for notifcation services. """

    def send_message(self, message, **kwargs):
        """
        Send a message.
        kwargs can contain ATTR_TITLE to specify a title.
        """
        raise NotImplementedError
