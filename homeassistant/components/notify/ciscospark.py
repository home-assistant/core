"""
Cisco Spark platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.ciscospark/
"""
import logging
import voluptuous as vol
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TITLE)
from homeassistant.const import (CONF_TOKEN)
import homeassistant.helpers.config_validation as cv

CONF_ROOMID = "roomid"

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['ciscosparkapi==0.4.2']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_ROOMID): cv.string,
})


# pylint: disable=unused-variable
def get_service(hass, config, discovery_info=None):
    """Get the CiscoSpark notification service."""
    return CiscoSparkNotificationService(
        config.get(CONF_TOKEN),
        config.get(CONF_ROOMID))


class CiscoSparkNotificationService(BaseNotificationService):
    """CiscoSparkNotificationService."""

    def __init__(self, token, default_room):
        """
        Initialize the service.

        Args:
            token: Cisco Spark Developer's Token
            default_room: Cisco Spark Room ID
        """
        from ciscosparkapi import CiscoSparkAPI
        self._default_room = default_room
        self._token = token
        self._spark = CiscoSparkAPI(access_token=self._token)

    def send_message(self, message="", **kwargs):
        """
        Send a message to a user.

        Args:
            message: notificaiton text
            kwargs: attributes used - 'title'
        """
        from ciscosparkapi import SparkApiError
        try:
            title = ""
            if kwargs.get(ATTR_TITLE) is not None:
                title = kwargs.get(ATTR_TITLE) + ": "
            self._spark.messages.create(roomId=self._default_room,
                                        text=title + message)
        except SparkApiError as api_error:
            _LOGGER.error("Could not send CiscoSpark notification. Error: %s",
                          api_error)
