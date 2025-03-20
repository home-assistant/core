"""clicksend_tts platform for notify component."""

from __future__ import annotations

from http import HTTPStatus
import json
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA as NOTIFY_PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_NAME,
    CONF_RECIPIENT,
    CONF_USERNAME,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

BASE_API_URL = "https://rest.clicksend.com/v3"

HEADERS = {"Content-Type": CONTENT_TYPE_JSON}

CONF_LANGUAGE = "language"
CONF_VOICE = "voice"

MALE_VOICE = "male"
FEMALE_VOICE = "female"

DEFAULT_NAME = "clicksend_tts"
DEFAULT_LANGUAGE = "en-us"
DEFAULT_VOICE = FEMALE_VOICE
TIMEOUT = 5

PLATFORM_SCHEMA = NOTIFY_PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_API_KEY): cv.string,
        vol.Required(CONF_RECIPIENT): vol.All(
            cv.string, vol.Match(r"^\+?[1-9]\d{1,14}$")
        ),
        vol.Optional(CONF_LANGUAGE, default=DEFAULT_LANGUAGE): cv.string,
        vol.Optional(CONF_VOICE, default=DEFAULT_VOICE): vol.In(
            [MALE_VOICE, FEMALE_VOICE]
        ),
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

    def __init__(self, config):
        """Initialize the service."""
        self.username = config[CONF_USERNAME]
        self.api_key = config[CONF_API_KEY]
        self.recipient = config[CONF_RECIPIENT]
        self.language = config[CONF_LANGUAGE]
        self.voice = config[CONF_VOICE]

    def send_message(self, message="", **kwargs):
        """Send a voice call to a user."""
        data = {
            "messages": [
                {
                    "source": "hass.notify",
                    "to": self.recipient,
                    "body": message,
                    "lang": self.language,
                    "voice": self.voice,
                }
            ]
        }
        api_url = f"{BASE_API_URL}/voice/send"
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
        response_msg = obj["response_msg"]
        response_code = obj["response_code"]
        _LOGGER.error(
            "Error %s : %s (Code %s)", resp.status_code, response_msg, response_code
        )


def _authenticate(config):
    """Authenticate with ClickSend."""
    api_url = f"{BASE_API_URL}/account"
    resp = requests.get(
        api_url,
        headers=HEADERS,
        auth=(config.get(CONF_USERNAME), config.get(CONF_API_KEY)),
        timeout=TIMEOUT,
    )

    return resp.status_code == HTTPStatus.OK
