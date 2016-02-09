"""
homeassistant.components.notify.rest
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
REST platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.rest/
"""
import logging
import requests

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, BaseNotificationService)

_LOGGER = logging.getLogger(__name__)

DEFAULT_METHOD = 'GET'
DEFAULT_PARAM_NAME = 'message'


def get_service(hass, config):
    """ Get the REST notification service. """

    if not validate_config({DOMAIN: config},
                           {DOMAIN: ['resource', ]},
                           _LOGGER):
        return None

    method = config.get('method', DEFAULT_METHOD)
    param_name = config.get('param_name', DEFAULT_PARAM_NAME)

    return RestNotificationService(config['resource'], method, param_name)


# pylint: disable=too-few-public-methods
class RestNotificationService(BaseNotificationService):
    """ Implements notification service for REST. """

    def __init__(self, resource, method=DEFAULT_METHOD,
                 param_name=DEFAULT_PARAM_NAME):
        self._resource = resource
        self._method = method
        self.param_name = param_name

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        data = {
            self.param_name: message
        }

        if self._method.upper() == 'GET':
            response = requests.get(self._resource, params=data)
        elif self._method.upper() == 'POST':
            response = requests.post(self._resource, data=data)
        elif self._method.upper() == 'JSON':
            response = requests.post(self._resource, json=data)

        if (response.status_code != requests.codes.ok and
                response.status_code != requests.codes.created):
            _LOGGER.exception(
                "Error sending message. Response: %s", response.reason)
