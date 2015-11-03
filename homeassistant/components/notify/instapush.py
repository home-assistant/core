"""
homeassistant.components.notify.instapush
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Instapush notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.instapush.html
"""
import logging
import json

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.instapush.im/v1/'


def get_service(hass, config):
    """ Get the instapush notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY,
                                     'app_secret',
                                     'event',
                                     'tracker']},
                           _LOGGER):
        return None

    try:
        import requests

    except ImportError:
        _LOGGER.exception(
            "Unable to import requests. "
            "Did you maybe not install the 'Requests' package?")

        return None

    # pylint: disable=unused-variable
    try:
        response = requests.get(_RESOURCE)

    except requests.ConnectionError:
        _LOGGER.error(
            "Connection error "
            "Please check if https://instapush.im is available.")

        return None

    instapush = requests.Session()
    headers = {'x-instapush-appid': config[DOMAIN][CONF_API_KEY],
               'x-instapush-appsecret': config[DOMAIN]['app_secret']}
    response = instapush.get(_RESOURCE + 'events/list',
                             headers=headers)

    try:
        if response.json()['error']:
            _LOGGER.error(response.json()['msg'])
    # pylint: disable=bare-except
    except:
        try:
            next(events for events in response.json()
                 if events['title'] == config[DOMAIN]['event'])
        except StopIteration:
            _LOGGER.error(
                "No event match your given value. "
                "Please create an event at https://instapush.im")
        else:
            return InstapushNotificationService(
                config[DOMAIN].get(CONF_API_KEY),
                config[DOMAIN]['app_secret'],
                config[DOMAIN]['event'],
                config[DOMAIN]['tracker']
                )


# pylint: disable=too-few-public-methods
class InstapushNotificationService(BaseNotificationService):
    """ Implements notification service for Instapush. """

    def __init__(self, api_key, app_secret, event, tracker):
        # pylint: disable=no-name-in-module, unused-variable
        from requests import Session

        self._api_key = api_key
        self._app_secret = app_secret
        self._event = event
        self._tracker = tracker
        self._headers = {
            'x-instapush-appid': self._api_key,
            'x-instapush-appsecret': self._app_secret,
            'Content-Type': 'application/json'}

        self.instapush = Session()

    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        data = {"event": self._event,
                "trackers": {self._tracker: title + " : " + message}}

        response = self.instapush.post(
            _RESOURCE + 'post',
            data=json.dumps(data),
            headers=self._headers)

        if response.json()['status'] == 401:
            _LOGGER.error(
                response.json()['msg'],
                "Please check your details at https://instapush.im/")
