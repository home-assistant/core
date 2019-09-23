"""Apprise platform for notify component."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)

_LOGGER = logging.getLogger(__name__)

CONF_FILE = "config"
CONF_URL = "url"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_URL): vol.All(cv.ensure_list, [str]),
        vol.Optional(CONF_FILE): cv.string
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the Apprise notification service."""
    from apprise import Apprise
    from apprise import AppriseConfig

    # Create our object
    a = Apprise()

    if config.get(CONF_FILE):
        # Sourced from a Configuration File
        ac = AppriseConfig()
        if not ac.add(config[CONF_FILE]):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

        elif not a.add(ac):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

    if config.get(CONF_URL):
        # Ordered list of URLs
        if not a.add(config[CONF_URL]):
            _LOGGER.error("Invalid Apprise URL(s) supplied")
            return None

    if len(a) == 0:
        _LOGGER.error("No Apprise services were loaded.")
        return None

    return AppriseNotificationService(a)


class AppriseNotificationService(BaseNotificationService):
    """Implement the notification service for Apprise."""

    def __init__(self, a_obj):
        """Initialize the service."""
        self.apprise = a_obj

    def send_message(self, message="", **kwargs):
        """Send a message to a specified target.
        """
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        self.apprise.notify(body=message, title=title)
