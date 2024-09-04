"""Clicksend platform for notify component."""

from __future__ import annotations

from http import HTTPStatus
import json
import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

BASE_API_URL = "https://rest.clicksend.com/v3"
DEFAULT_SENDER = "hass"
TIMEOUT = 5

HEADERS = {"Content-Type": CONTENT_TYPE_JSON}


PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_RECIPIENT, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_SENDER, default=DEFAULT_SENDER): cv.string,
    }
)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: DiscoveryInfoType | None = None,
) -> ClicksendNotificationService | None:
    """Get the ClickSend notification service."""
    if not _authenticate(config):
        _LOGGER.error("You are not authorized to access ClickSend")
        return None
    return ClicksendNotificationService(config)


class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the ClickSend service."""

    def __init__(self, config: ConfigType) -> None:
        """Initialize the service."""
        self.username: str = config[CONF_USERNAME]
        self.api_key: str = config[CONF_API_KEY]
        self.recipients: list[str] = config[CONF_RECIPIENT]
        self.sender: str = config[CONF_SENDER]

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""
        data: dict[str, Any] = {"messages": []}
        for recipient in self.recipients:
            data["messages"].append(
                {
                    "source": "hass.notify",
                    "from": self.sender,
                    "to": recipient,
                    "body": message,
                }
            )

        api_url = f"{BASE_API_URL}/sms/send"
        resp = requests.post(
            api_url,
            data=json.dumps(data),
            headers=HEADERS,
            auth=(self.username, self.api_key),
            timeout=TIMEOUT,
        )
        if resp.status_code == HTTPStatus.OK:
            return

        obj = json.loads(resp.text)
        response_msg = obj.get("response_msg")
        response_code = obj.get("response_code")
        _LOGGER.error(
            "Error %s : %s (Code %s)", resp.status_code, response_msg, response_code
        )


def _authenticate(config: ConfigType) -> bool:
    """Authenticate with ClickSend."""
    api_url = f"{BASE_API_URL}/account"
    resp = requests.get(
        api_url,
        headers=HEADERS,
        auth=(config[CONF_USERNAME], config[CONF_API_KEY]),
        timeout=TIMEOUT,
    )
    return resp.status_code == HTTPStatus.OK
