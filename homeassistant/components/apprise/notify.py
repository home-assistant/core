"""Apprise platform for notify component."""
from __future__ import annotations

import logging
from typing import Any

import apprise
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

CONF_FILE = "config"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_URL): vol.All(cv.ensure_list, [str]),
        vol.Optional(CONF_FILE): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> AppriseNotificationService | None:
    """Get the Apprise notification service."""
    # Create our Apprise Instance (reference our asset)
    a_obj = apprise.Apprise()

    if config.get(CONF_FILE):
        # Sourced from a Configuration File
        a_config = apprise.AppriseConfig()
        if not a_config.add(config[CONF_FILE]):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

        if not a_obj.add(a_config):
            _LOGGER.error("Invalid Apprise config url provided")
            return None

    # Ordered list of URLs
    if config.get(CONF_URL) and not a_obj.add(config[CONF_URL]):
        _LOGGER.error("Invalid Apprise URL(s) supplied")
        return None

    return AppriseNotificationService(a_obj)


class AppriseNotificationService(BaseNotificationService):
    """Implement the notification service for Apprise."""

    def __init__(self, a_obj: apprise.Apprise) -> None:
        """Initialize the service."""
        self.apprise = a_obj

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a specified target.

        If no target/tags are specified, then services are notified as is
        However, if any tags are specified, then they will be applied
        to the notification causing filtering (if set up that way).
        """
        targets = kwargs.get(ATTR_TARGET)
        title = kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT)
        self.apprise.notify(body=message, title=title, tag=targets)
