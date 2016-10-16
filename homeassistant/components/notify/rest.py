"""
RESTful platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.rest/
"""
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_TITLE_DEFAULT, BaseNotificationService,
    PLATFORM_SCHEMA)
from homeassistant.const import (CONF_RESOURCE, CONF_METHOD, CONF_NAME)
import homeassistant.helpers.config_validation as cv

CONF_MESSAGE_PARAMETER_NAME = 'message_param_name'
CONF_TARGET_PARAMETER_NAME = 'target_param_name'
CONF_TITLE_PARAMETER_NAME = 'title_param_name'
DEFAULT_MESSAGE_PARAM_NAME = 'message'
DEFAULT_METHOD = 'GET'
DEFAULT_TARGET_PARAM_NAME = None
DEFAULT_TITLE_PARAM_NAME = None

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_RESOURCE): cv.url,
    vol.Optional(CONF_MESSAGE_PARAMETER_NAME,
                 default=DEFAULT_MESSAGE_PARAM_NAME): cv.string,
    vol.Optional(CONF_METHOD, default=DEFAULT_METHOD):
        vol.In(['POST', 'GET', 'POST_JSON']),
    vol.Optional(CONF_NAME): cv.string,
    vol.Optional(CONF_TARGET_PARAMETER_NAME,
                 default=DEFAULT_TARGET_PARAM_NAME): cv.string,
    vol.Optional(CONF_TITLE_PARAMETER_NAME,
                 default=DEFAULT_TITLE_PARAM_NAME): cv.string,
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config):
    """Get the RESTful notification service."""
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    message_param_name = config.get(CONF_MESSAGE_PARAMETER_NAME)
    title_param_name = config.get(CONF_TITLE_PARAMETER_NAME)
    target_param_name = config.get(CONF_TARGET_PARAMETER_NAME)

    return RestNotificationService(
        resource, method, message_param_name, title_param_name,
        target_param_name)


# pylint: disable=too-few-public-methods, too-many-arguments
class RestNotificationService(BaseNotificationService):
    """Implementation of a notification service for REST."""

    def __init__(self, resource, method, message_param_name, title_param_name,
                 target_param_name):
        """Initialize the service."""
        self._resource = resource
        self._method = method.upper()
        self._message_param_name = message_param_name
        self._title_param_name = title_param_name
        self._target_param_name = target_param_name

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            self._message_param_name: message
        }

        if self._title_param_name is not None:
            data[self._title_param_name] = kwargs.get(ATTR_TITLE,
                                                      ATTR_TITLE_DEFAULT)

        if self._target_param_name is not None and ATTR_TARGET in kwargs:
            # Target is a list as of 0.29 and we don't want to break existing
            # integrations, so just return the first target in the list.
            data[self._target_param_name] = kwargs[ATTR_TARGET][0]

        if self._method == 'POST':
            response = requests.post(self._resource, data=data, timeout=10)
        elif self._method == 'POST_JSON':
            response = requests.post(self._resource, json=data, timeout=10)
        else:   # default GET
            response = requests.get(self._resource, params=data, timeout=10)

        if response.status_code not in (200, 201):
            _LOGGER.exception(
                "Error sending message. Response %d: %s:",
                response.status_code, response.reason)
