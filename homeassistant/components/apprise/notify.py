"""Apprise platform for notify component."""
import logging

import apprise
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
import homeassistant.helpers.config_validation as cv

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

    # Create our Apprise Asset Object
    asset = apprise.AppriseAsset(async_mode=False)

    # Create our Apprise Instance (reference our asset)
    a_obj = apprise.Apprise(asset=asset)

    if config.get(CONF_FILE):
        # Sourced from a Configuration File
        a_config = apprise.AppriseConfig()
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

    return AppriseNotificationService(a_obj)


class AppriseNotificationService(BaseNotificationService):
    """Implement the notification service for Apprise."""

    def __init__(self, a_obj):
        """Initialize the service."""
        self.apprise = a_obj

    def send_message(self, message="", **kwargs):
        """Send a message to a specified target.

        If no target/tags are specified, then services are notified as is
        However, if any tags are specified, then they will be applied
        to the notification causing filtering (if set up that way).
        """
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        self.apprise.notify(body=message, title=title, tag=targets)
