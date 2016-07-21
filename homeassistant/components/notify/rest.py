"""
REST platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.rest/
"""
import logging

import requests

from homeassistant.const import CONF_NAME
from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_MESSAGE_PARAM_NAME = 'message'
DEFAULT_TITLE_PARAM_NAME = None
DEFAULT_TARGET_PARAM_NAME = None


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Get the REST notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['resource', ]},
                           _LOGGER):
        return False

    method = config.get('method', DEFAULT_METHOD)
    message_param_name = config.get('message_param_name',
                                    DEFAULT_MESSAGE_PARAM_NAME)
    title_param_name = config.get('title_param_name',
                                  DEFAULT_TITLE_PARAM_NAME)
    target_param_name = config.get('target_param_name',
                                   DEFAULT_TARGET_PARAM_NAME)

    add_devices([RestNotificationService(
        config.get('resource'),
        method,
        message_param_name,
        title_param_name,
        target_param_name,
        config.get(CONF_NAME))])


# pylint: disable=too-few-public-methods,too-many-arguments,abstract-method
class RestNotificationService(BaseNotificationService):
    """Implement the notification service for REST."""

    def __init__(self, resource, method, message_param_name,
                 title_param_name, target_param_name, name):
        """Initialize the service."""
        self._resource = resource
        self._method = method.upper()
        self._message_param_name = message_param_name
        self._title_param_name = title_param_name
        self._target_param_name = target_param_name
        self._name = name

    @property
    def name(self):
        """Return name of notification entity."""
        return self._name

    def send_message(self, message, **kwargs):
        """Send a message to a user."""
        data = {
            self._message_param_name: message
        }

        if self._title_param_name is not None:
            data[self._title_param_name] = kwargs.get(ATTR_TITLE)

        if self._target_param_name is not None:
            data[self._target_param_name] = kwargs.get(ATTR_TARGET)

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
