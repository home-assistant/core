"""ntfy platform for notify component."""
from __future__ import annotations

import logging
from typing import Any

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

CONF_TOPIC = "topic"
DEFAULT_URL = "https://ntfy.sh"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        # have to set topic globally in the configuration, can override in "data"
        vol.Required(CONF_TOPIC): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: Any = None,  # pylint: disable=hass-argument-type
) -> BaseNotificationService:
    """Get the ntfy notification service."""
    url = str(config.get(CONF_URL))
    topic = str(config.get(CONF_TOPIC))
    username = config.get(CONF_USERNAME)  # could be None since optional
    password = config.get(CONF_PASSWORD)  # could be None since optional
    verify_ssl = bool(config.get(CONF_VERIFY_SSL))

    if username and password:
        auth = requests.auth.HTTPBasicAuth(str(username), str(password))
    else:
        auth = None

    return NtfyNotificationService(
        hass,
        url=url,
        topic=topic,
        auth=auth,
        verify_ssl=verify_ssl,
    )


class NtfyNotificationService(BaseNotificationService):
    """Implementation of a notification service for ntfy."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        url: str,
        topic: str,
        auth: requests.auth.HTTPBasicAuth | None,
        verify_ssl: bool,
    ) -> None:
        """Initialize the service."""
        self._hass = hass
        self._url = url
        self._topic = topic
        self._auth = auth
        self._verify_ssl = verify_ssl

    def send_message(self, message: str = "", **kwargs: Any) -> None:
        """Send a message to a user."""

        post_data = {
            "topic": self._topic,
            "message": message,
            "title": kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
        }

        extra_data = kwargs.get(ATTR_DATA, {})
        # If additional data provided by user
        if extra_data:
            # Override properties with elements from extra data
            extra_data_keys = extra_data.keys()
            if "message" in extra_data_keys:
                post_data["message"] = extra_data["message"]

            if "topic" in extra_data_keys:
                post_data["topic"] = extra_data["topic"]

            if "title" in extra_data_keys:
                post_data["title"] = extra_data["title"]

        response = requests.post(
            self._url,
            json=post_data,
            timeout=10,
            auth=self._auth,
            verify=self._verify_ssl,
        )

        try:
            response.raise_for_status()  # raise an error if a 4xx or 5xx response is returned
        except requests.exceptions.HTTPError:
            _LOGGER.exception(
                "Error communicating with ntfy. Response %d: %s",
                response.status_code,
                response.reason,
            )

        _LOGGER.debug("Response %d: %s", response.status_code, response.reason)
