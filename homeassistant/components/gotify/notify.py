"""Gotify platform for notify component."""
import logging

import gotify

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN

from .const import ATTR_LINK, ATTR_PRIORITY, DOMAIN

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Gotify notification service."""
    config_entry = hass.data[DOMAIN][discovery_info["entry_id"]]
    return GotifyNotificationService(
        config_entry.data[CONF_TOKEN], config_entry.data[CONF_HOST]
    )


class GotifyNotificationService(BaseNotificationService):
    """Implement the notification service for Gotify."""

    def __init__(self, token, url):
        """Initialize the service."""
        self.token = token
        self.url = url
        self.gotify = gotify.gotify(
            base_url=url,
            app_token=token,
        )

    def send_message(self, message, **kwargs):
        """Send a message."""
        data = kwargs.get(ATTR_DATA) or {}
        title = kwargs.get(ATTR_TITLE) or None
        priority = data.get(ATTR_PRIORITY) or 4
        link = data.get(ATTR_LINK) or ""

        extras = {
            "client::display": {"contentType": "text/markdown"},
            "client::notification": {
                "click": {"url": "homeassistant://navigate/" + link}
            },
        }

        try:
            self.gotify.create_message(
                message, title=title, priority=priority, extras=extras
            )
        except gotify.GotifyError as exception:
            _LOGGER.error("Send message failed: %s", str(exception))
