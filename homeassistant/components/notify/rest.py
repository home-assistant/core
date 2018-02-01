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

CONF_DATA = 'data'
CONF_DATA_TEMPLATE = 'data_template'
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
    vol.Optional(CONF_DATA,
                 default=None): dict,
    vol.Optional(CONF_DATA_TEMPLATE,
                 default=None): {cv.match_all: cv.template_complex}
})

_LOGGER = logging.getLogger(__name__)


def get_service(hass, config, discovery_info=None):
    """Get the RESTful notification service."""
    resource = config.get(CONF_RESOURCE)
    method = config.get(CONF_METHOD)
    message_param_name = config.get(CONF_MESSAGE_PARAMETER_NAME)
    title_param_name = config.get(CONF_TITLE_PARAMETER_NAME)
    target_param_name = config.get(CONF_TARGET_PARAMETER_NAME)
    data = config.get(CONF_DATA)
    data_template = config.get(CONF_DATA_TEMPLATE)

    return RestNotificationService(
        hass, resource, method, message_param_name,
        title_param_name, target_param_name, data, data_template)


class RestNotificationService(BaseNotificationService):
    """Implementation of a notification service for REST."""

    def __init__(self, hass, resource, method, message_param_name,
                 title_param_name, target_param_name, data, data_template):
        """Initialize the service."""
        self._resource = resource
        self._hass = hass
        self._method = method.upper()
        self._message_param_name = message_param_name
        self._title_param_name = title_param_name
        self._target_param_name = target_param_name
        self._data = data
        self._data_template = data_template

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        data = {
            self._message_param_name: message
        }

        if self._title_param_name is not None:
            data[self._title_param_name] = kwargs.get(
                ATTR_TITLE, ATTR_TITLE_DEFAULT)

        if self._target_param_name is not None and ATTR_TARGET in kwargs:
            # Target is a list as of 0.29 and we don't want to break existing
            # integrations, so just return the first target in the list.
            data[self._target_param_name] = kwargs[ATTR_TARGET][0]

        if self._data:
            data.update(self._data)
        elif self._data_template:
            def _data_template_creator(value):
                """Recursive template creator helper function."""
                if isinstance(value, list):
                    return [_data_template_creator(item) for item in value]
                elif isinstance(value, dict):
                    return {key: _data_template_creator(item)
                            for key, item in value.items()}
                value.hass = self._hass
                return value.async_render(kwargs)
            data.update(_data_template_creator(self._data_template))

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
