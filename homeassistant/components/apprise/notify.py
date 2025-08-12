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
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_FILE_URL

_LOGGER = logging.getLogger(__name__)


PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_URL): vol.All(cv.ensure_list, [str]),
        vol.Optional(CONF_FILE_URL): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> AppriseNotificationService | None:
    """Get the Apprise notification service."""
    # Create our Apprise Instance (reference our asset)
    _LOGGER.debug("Apprise discovery_info: %s", discovery_info)

    if not discovery_info:
        return None

    a_obj = apprise.Apprise()

    if CONF_FILE_URL in discovery_info:
        # Sourced from a Configuration File
        a_config = apprise.AppriseConfig()
        conf_urls = discovery_info[CONF_FILE_URL]
        if isinstance(conf_urls, str):
            conf_urls = [conf_urls]
        for url in conf_urls:
            a_config.add(url)

        a_obj.add(a_config)

    # Ordered list of URLs
    if CONF_URL in discovery_info:
        urls = discovery_info[CONF_URL]
        if isinstance(urls, str):
            urls = [urls]
        for url in urls:
            a_obj.add(url)

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
