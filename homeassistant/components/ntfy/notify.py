"""ntfy platform for notify component."""
from http import HTTPStatus
import logging
from typing import Any, Union

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    ATTR_MESSAGE,
    ATTR_TITLE,
    ATTR_TITLE_DEFAULT,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import (
    CONF_AUTHENTICATION,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    HTTP_BASIC_AUTHENTICATION,
    HTTP_DIGEST_AUTHENTICATION,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

CONF_TOPIC = "topic"
DEFAULT_URL = "https://ntfy.sh"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(
            CONF_TOPIC
        ): cv.string,  # have to set topic globally in the configuration, can override in "data"
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_URL, default=DEFAULT_URL): cv.url,
        vol.Optional(CONF_AUTHENTICATION): vol.In(
            [HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION]
        ),
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_USERNAME): cv.string,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(
    hass: HomeAssistant,
    config: ConfigType,
    discovery_info: Union[DiscoveryInfoType, None] = None,
) -> BaseNotificationService:
    """Get the ntfy notification service."""
    url = config.get(CONF_URL)
    topic = config.get(CONF_TOPIC)
    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    if username and password:
        if config.get(CONF_AUTHENTICATION) == HTTP_DIGEST_AUTHENTICATION:
            auth = requests.auth.HTTPDigestAuth(username, password)
        else:
            auth = requests.auth.HTTPBasicAuth(username, password)
    else:
        auth = None

    return NtfyNotificationService(
        hass,
        url,
        topic,
        auth,
        verify_ssl,
    )


class NtfyNotificationService(BaseNotificationService):
    """Implementation of a notification service for ntfy."""

    def __init__(
        self,
        hass,
        url,
        topic,
        auth,
        verify_ssl,
    ):
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

        # Ignore target

        extra_data = kwargs.get(ATTR_DATA, {})
        # If additional data parameters provided by user
        if extra_data:
            # Add message and topic to kwargs
            kwargs[ATTR_MESSAGE] = message
            kwargs[CONF_TOPIC] = self._topic

            # Title already exists in kwargs

            def _data_template_creator(value):
                """Recursive template creator helper function."""
                if isinstance(value, dict):
                    return value

                # Parsing error (data is not a dictionary)
                value.hass = self._hass
                return value.async_render(kwargs, parse_result=False)

            # Combine additional data with message and title in JSON body
            post_data.update(_data_template_creator(extra_data))

        response = requests.post(
            self._url,
            json=post_data,
            timeout=10,
            auth=self._auth,
            verify=self._verify_ssl,
        )

        if (
            response.status_code >= HTTPStatus.INTERNAL_SERVER_ERROR
            and response.status_code < 600
        ):
            _LOGGER.exception(
                "Server error. Response %d: %s:", response.status_code, response.reason
            )
        elif (
            response.status_code >= HTTPStatus.BAD_REQUEST
            and response.status_code < HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            _LOGGER.exception(
                "Client error. Response %d: %s:", response.status_code, response.reason
            )
        elif (
            response.status_code >= HTTPStatus.OK
            and response.status_code < HTTPStatus.MULTIPLE_CHOICES
        ):
            _LOGGER.debug(
                "Success. Response %d: %s:", response.status_code, response.reason
            )
        else:
            _LOGGER.debug("Response %d: %s:", response.status_code, response.reason)
