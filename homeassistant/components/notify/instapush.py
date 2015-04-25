"""
homeassistant.components.notify.instapush
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Instapush notification service.

Configuration:

To use the Instapush notifier you will need to add something like the following
to your config/configuration.yaml

notify:
  platform: instapush
  api_key: YOUR_APP_KEY
  app_secret: YOUR_APP_SECRET
  event: YOUR_EVENT
  tracker: YOUR_TRACKER

VARIABLES:

api_key
*Required
To retrieve this value log into your account at https://instapush.im and go
to 'APPS'.

app_secret
*Required
To get this value log into your account at https://instapush.im and go to
'APPS'. The 'Application ID' can be found under 'Basic Info'. Make sure that
you have at least one event for your app.

event
*Required
To retrieve this value log into your account at https://instapush.im and go
to 'APPS'.

tracker
*Required
To retrieve this value log into your account at https://instapush.im and go
to 'APPS'.

Example usage of Instapush if you have an event 'notification' and a tracker
'home-assistant'.

curl -X POST \
    -H "x-instapush-appid: YOUR_APP_KEY" \
    -H "x-instapush-appsecret: YOUR_APP_SECRET" \
    -H "Content-Type: application/json" \
      -d '{"event":"notification","trackers":{"home-assistant":"Switch 1"}}' \
    https://api.instapush.im/v1/post

Details for the API : https://instapush.im/developer/rest

"""
import logging
import json

from homeassistant.helpers import validate_config
from homeassistant.components.notify import (
    DOMAIN, ATTR_TITLE, BaseNotificationService)
from homeassistant.const import CONF_API_KEY

_LOGGER = logging.getLogger(__name__)
_RESOURCE = 'https://api.instapush.im/v1/post'


def get_service(hass, config):
    """ Get the instapush notification service. """

    if not validate_config(config,
                           {DOMAIN: [CONF_API_KEY, 'app_secret', \
                                'event', 'tracker']},
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
        from requests import Request, Session

        self._api_key = api_key
        self._app_secret = app_secret
        self._event = event
        self._tracker = tracker
        self._headers = {
            'X-INSTAPUSH-APPID' : self._api_key,
            'X-INSTAPUSH-APPSECRET' : self._app_secret,
            'Content-Type' : 'application/json'}

        self.instapush = Session()


    def send_message(self, message="", **kwargs):
        """ Send a message to a user. """

        title = kwargs.get(ATTR_TITLE)

        data = {"event":self._event,
                "trackers":{self._tracker:title + " : " + message}}

        response = self.instapush.post(
            _RESOURCE,
            data=json.dumps(data),
            headers=self._headers)

        if response.json()['error'] == 'True':
            _LOGGER.error(
                "Wrong details supplied. "
                "Get them at https://instapush.im/")
