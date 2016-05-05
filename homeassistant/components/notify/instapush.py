"""
Instapush notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.instapush/
"""
import json
import logging

import requests

from homeassistant.components.notify import (
    ATTR_TITLE, DOMAIN, BaseNotificationService)
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers import validate_config

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.instapush.im/v1/'


def get_service(hass, config):
    """Get the instapush notification service."""
    if not validate_config({DOMAIN: config},
                           {DOMAIN: [CONF_API_KEY,
                                     'app_secret',
                                     'event',
                                     'tracker']},
                           _LOGGER):
        return None

    headers = {'x-instapush-appid': config[CONF_API_KEY],
               'x-instapush-appsecret': config['app_secret']}

    try:
        response = requests.get(_RESOURCE + 'events/list',
                                headers=headers).json()
    except ValueError:
        _LOGGER.error('Unexpected answer from Instapush API.')
        return None

    if 'error' in response:
        _LOGGER.error(response['msg'])
        return None

    if len([app for app in response if app['title'] == config['event']]) == 0:
        _LOGGER.error(
            "No app match your given value. "
            "Please create an app at https://instapush.im")
        return None

    return InstapushNotificationService(
        config[CONF_API_KEY], config['app_secret'], config['event'],
        config['tracker'])


# pylint: disable=too-few-public-methods
class InstapushNotificationService(BaseNotificationService):
    """Implement the notification service for Instapush."""

    def __init__(self, api_key, app_secret, event, tracker):
        """Initialize the service."""
        self._api_key = api_key
        self._app_secret = app_secret
        self._event = event
        self._tracker = tracker
        self._headers = {
            'x-instapush-appid': self._api_key,
            'x-instapush-appsecret': self._app_secret,
            'Content-Type': 'application/json'}

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        title = kwargs.get(ATTR_TITLE)
        data = {"event": self._event,
                "trackers": {self._tracker: title + " : " + message}}

        response = requests.post(_RESOURCE + 'post', data=json.dumps(data),
                                 headers=self._headers)

        if response.json()['status'] == 401:
            _LOGGER.error(
                response.json()['msg'],
                "Please check your details at https://instapush.im/")
