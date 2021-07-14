"""Gotify platform for notify component."""
import json
import logging

import requests

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    BaseNotificationService,
)
from homeassistant.const import CONF_TOKEN, CONF_URL

from .const import DOMAIN

ATTR_LEVEL = "level"
ATTR_PRIORITY = "priority"
ATTR_TOKEN = "token"
ATTR_URL = "url"
ATTR_LINK = "link"

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Notify.Events notification service."""
    return NotifyEventsNotificationService(
        hass.data[DOMAIN][CONF_TOKEN], hass.data[DOMAIN][CONF_URL]
    )


class NotifyEventsNotificationService(BaseNotificationService):
    """Implement the notification service for Notify.Events."""

    def __init__(self, token, url):
        """Initialize the service."""
        self.token = token
        self.url = url

    def send_message(self, message, **kwargs):
        """Send a message."""
        data = kwargs.get(ATTR_DATA) or {}
        token = data.get(ATTR_TOKEN, self.token)
        title = kwargs.get(ATTR_TITLE) or {}
        priority = data.get(ATTR_PRIORITY) or 4
        url = data.get(ATTR_URL, self.url)
        link = data.get(ATTR_LINK) or ""

        headers = {"Content-Type": "application/json"}

        request_url = url + "/message?token=" + token

        request_dict = {
            "message": message,
            "priority": priority,
            "extras": {
                "client::display": {"contentType": "text/markdown"},
                "client::notification": {
                    "click": {"url": "homeassistant://navigate/" + link}
                },
            },
        }

        if title:
            request_dict["title"] = title

        request_json = json.dumps(request_dict)

        resp = requests.request(
            method="POST", url=request_url, headers=headers, data=request_json
        )

        if resp.status_code != 200:
            _LOGGER.error("API POST Error: %s", resp.text)
