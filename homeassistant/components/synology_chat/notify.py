"""SynologyChat platform for notify component."""
import json
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_DATA,
    PLATFORM_SCHEMA,
    BaseNotificationService,
)
from homeassistant.const import CONF_RESOURCE, CONF_VERIFY_SSL, HTTP_OK
import homeassistant.helpers.config_validation as cv

ATTR_FILE_URL = "file_url"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_RESOURCE): cv.url,
        vol.Optional(CONF_VERIFY_SSL, default=True): cv.boolean,
    }
)

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the Synology Chat notification service."""
    resource = config.get(CONF_RESOURCE)
    verify_ssl = config.get(CONF_VERIFY_SSL)

    return SynologyChatNotificationService(resource, verify_ssl)


class SynologyChatNotificationService(BaseNotificationService):
    """Implementation of a notification service for Synology Chat."""

    def __init__(self, resource, verify_ssl):
        """Initialize the service."""
        self._resource = resource
        self._verify_ssl = verify_ssl

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {"text": message}

        extended_data = kwargs.get(ATTR_DATA)
        file_url = extended_data.get(ATTR_FILE_URL) if extended_data else None

        if file_url:
            data["file_url"] = file_url

        to_send = "payload={}".format(json.dumps(data))

        response = requests.post(
            self._resource, data=to_send, timeout=10, verify=self._verify_ssl
        )

        if response.status_code not in (HTTP_OK, 201):
            _LOGGER.exception(
                "Error sending message. Response %d: %s:",
                response.status_code,
                response.reason,
            )
