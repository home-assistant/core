"""Clickatell platform for notify component."""

from __future__ import annotations

from http import HTTPStatus
import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_API_KEY, CONF_RECIPIENT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "clickatell"

BASE_API_URL = "https://platform.clickatell.com/messages/http/send"

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_API_KEY): cv.string, vol.Required(CONF_RECIPIENT): cv.string}
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ClickatellNotificationService:
    """Get the Clickatell notification service."""
    return ClickatellNotificationService(config)


class ClickatellNotificationService(BaseNotificationService):
    """Implementation of a notification service for the Clickatell service."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the service."""
        self.api_key: str = config[CONF_API_KEY]
        self.recipient: str = config[CONF_RECIPIENT]

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        data = {"apiKey": self.api_key, "to": self.recipient, "content": message}

        resp = requests.get(BASE_API_URL, params=data, timeout=5)
        if resp.status_code not in (HTTPStatus.OK, HTTPStatus.ACCEPTED):
            _LOGGER.error("Error %s : %s", resp.status_code, resp.text)
