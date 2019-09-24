"""Apprise platform for notify component."""
import logging

import voluptuous as vol

from apprise import Apprise, AppriseConfig

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
        vol.Optional(CONF_FILE): cv.string,
    }
)


def get_service(hass, config, discovery_info=None):
    """Get the Apprise notification service."""

    # Create our object
    a_obj = Apprise()

    if config.get(CONF_FILE):
        # Sourced from a Configuration File
        a_config = AppriseConfig()
        if not a_config.add(config[CONF_FILE]):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

        if not a_obj.add(a_config):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

    if config.get(CONF_URL):
        # Ordered list of URLs
        if not a_obj.add(config[CONF_URL]):
            _LOGGER.error("Invalid Apprise URL(s) supplied")
            return None

    loaded = len(a_obj)
    if not loaded:
        _LOGGER.error("No Apprise services were loaded.")
        return None

    _LOGGER.info("Loaded %d Apprise service(s).", loaded)
    return AppriseNotificationService(a_obj)


class AppriseNotificationService(BaseNotificationService):
    """Implement the notification service for Apprise."""

    def __init__(self, a_obj):
        """Initialize the service."""
        self.apprise = a_obj

    def send_message(self, message="", **kwargs):
        """Send a message to a specified target."""
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        self.apprise.notify(body=message, title=title)
