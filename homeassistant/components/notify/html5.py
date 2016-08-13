"""
HTML5 Push Messaging notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.html5/
"""
import os
import logging
import json

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import HTTP_BAD_REQUEST
from homeassistant.util import ensure_unique_string
from homeassistant.components.notify import (ATTR_TARGET,
                                             BaseNotificationService)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.frontend import add_manifest_json_key
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['https://github.com/web-push-libs/pywebpush/archive/'
                'e743dc92558fc62178d255c0018920d74fa778ed.zip#'
                'pywebpush==0.5.0', 'cryptography==1.4']

DEPENDENCIES = ["frontend"]

_LOGGER = logging.getLogger(__name__)

REGISTRATIONS_FILE = "html5_push_registrations.conf"

CONF_SUBSCRIPTION = 'subscription'
CONF_BROWSER = 'browser'
REGISTER_SCHEMA = vol.Schema({
    vol.Required(CONF_SUBSCRIPTION): cv.match_all,
    vol.Required(CONF_BROWSER): vol.In(['chrome', 'firefox'])
})


def config_from_file(filename, config=None):
    """Small configuration file management function."""
    if config:
        # We"re writing configuration
        try:
            with open(filename, "w") as fdesc:
                fdesc.write(json.dumps(config))
        except IOError as error:
            _LOGGER.error("Saving config file failed: %s", error)
            return False
        return True
    else:
        # We"re reading config
        if os.path.isfile(filename):
            try:
                with open(filename, "r") as fdesc:
                    return json.loads(fdesc.read())
            except IOError as error:
                _LOGGER.error("Reading config file failed: %s", error)
                # This won"t work yet
                return False
        else:
            return {}


class HTML5PushRegistrationView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    url = "/api/notify.html5"
    name = "api:notify.html5"

    def __init__(self, hass, registrations, json_path):
        """Init HTML5PushRegistrationView."""
        super().__init__(hass)
        self.registrations = registrations
        self.json_path = json_path

    def post(self, request):
        """Accept the POST request for push registrations from a browser."""

        try:
            data = REGISTER_SCHEMA(request.json)
        except vol.Invalid as ex:
            return self.json_message(humanize_error(request.json, ex),
                                     HTTP_BAD_REQUEST)

        name = ensure_unique_string('unnamed device',
                                    self.registrations.keys())

        self.registrations[name] = data

        print(data)
        print(type(data))

        if not config_from_file(self.json_path, self.registrations):
            return self.json_message(humanize_error(request.json, ex),
                                     HTTP_BAD_REQUEST)

        return self.json_message("Push notification subscriber registered.")


def get_service(hass, config):
    """Get the HTML5 push notification service."""
    json_path = hass.config.path(REGISTRATIONS_FILE)
    registrations = config_from_file(json_path)

    hass.wsgi.register_view(
        HTML5PushRegistrationView(hass, registrations, json_path))

    gcm_api_key = config.get('gcm_api_key', None)
    gcm_sender_id = config.get('gcm_sender_id')

    if gcm_sender_id is not None:
        add_manifest_json_key('gcm_sender_id', config.get('gcm_sender_id'))

    return HTML5NotificationService(gcm_api_key, registrations)


# pylint: disable=too-few-public-methods
class HTML5NotificationService(BaseNotificationService):
    """Implement the notification service for HTML5."""

    # pylint: disable=too-many-arguments
    def __init__(self, gcm_key, registrations):
        """Initialize the service."""
        self._gcm_key = gcm_key
        self.registrations = registrations

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pywebpush import WebPusher
        payload = {"body": message}
        payload.update(dict((k, v) for k, v in kwargs.items() if v))
        if kwargs.get('icon') is None:
            payload['icon'] = '/static/icons/favicon-192x192.png'

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = self.registrations.keys()
        elif not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            if self.registrations.get(target) is None:
                _LOGGER.error("%s is not a valid HTML5 push notification"
                              " target!", target)
                continue
            WebPusher(self.registrations[target][CONF_SUBSCRIPTION]).send(
                json.dumps(payload), gcm_key=self._gcm_key)
