"""Clicksend platform for notify component."""
from http import HTTPStatus
import json
import logging

import aiohttp
import voluptuous as vol

from homeassistant.components.notify import PLATFORM_SCHEMA, BaseNotificationService
from homeassistant.const import (
    CONF_API_KEY,
    CONF_RECIPIENT,
    CONF_SENDER,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
)
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

BASE_API_URL = "https://rest.clicksend.com/v3"
DEFAULT_SENDER = "hass"
TIMEOUT = 5

HEADERS = {"Content-Type": CONTENT_TYPE_JSON}


PLATFORM_SCHEMA = vol.Schema(
    vol.All(
        PLATFORM_SCHEMA.extend(
            {
                vol.Required(CONF_USERNAME): cv.string,
                vol.Required(CONF_API_KEY): cv.string,
                vol.Required(CONF_RECIPIENT, default=[]): vol.All(
                    cv.ensure_list, [cv.string]
                ),
                vol.Optional(CONF_SENDER, default=DEFAULT_SENDER): cv.string,
            }
        )
    )
)


async def get_service(hass, config, discovery_info=None):
    """Get the ClickSend notification service."""
    if not await _authenticate(config):
        _LOGGER.error("You are not authorized to access ClickSend")
        return None
    return ClicksendNotificationService(config)


class ClicksendNotificationService(BaseNotificationService):
    """Implementation of a notification service for the ClickSend service."""

    def __init__(self, config):
        """Initialize the service."""
        self.username = config[CONF_USERNAME]
        self.api_key = config[CONF_API_KEY]
        self.recipients = config[CONF_RECIPIENT]
        self.sender = config[CONF_SENDER]

    async def async_send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {"messages": []}
        for recipient in self.recipients.split(","):
            data["messages"].append(
                {
                    "source": "hass.notify",
                    "from": self.sender,
                    "to": recipient.strip(),
                    "body": message,
                }
            )

        api_url = f"{BASE_API_URL}/sms/send"
        async with aiohttp.ClientSession(headers=HEADERS) as session:
            async with session.post(
                api_url,
                data=json.dumps(data).encode("utf-8"),
                auth=aiohttp.BasicAuth(self.username, self.api_key),
            ) as resp:
                if resp.status == HTTPStatus.OK:
                    return
                obj = await resp.json()
                response_msg = obj.get("response_msg")
                response_code = obj.get("response_code")
                _LOGGER.error(
                    "Error %s : %s (Code %s)",
                    resp.status_code,
                    response_msg,
                    response_code,
                )


async def _authenticate(config):
    """Authenticate with ClickSend."""
    url = f"{BASE_API_URL}/account"
    async with aiohttp.ClientSession(headers=HEADERS) as session:
        async with session.get(
            url, auth=aiohttp.BasicAuth(config[CONF_USERNAME], config[CONF_API_KEY])
        ) as resp:
            received = resp.status == 200
            payload = await resp.json()

            if received:
                active = payload["data"]["active"] == 1
                if active:
                    return True
                return False
            return False
