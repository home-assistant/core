"""
Chrome Push Messaging notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.chrome/
"""
import os
import logging
import json

from homeassistant.components.notify import (ATTR_TARGET,
                                             BaseNotificationService)
from homeassistant.components.http import HomeAssistantView

REQUIREMENTS = ['https://github.com/web-push-libs/pywebpush/archive/'
                'e743dc92558fc62178d255c0018920d74fa778ed.zip#'
                'pywebpush==0.5.0']

DEPENDENCIES = ["http"]

_LOGGER = logging.getLogger(__name__)

REGISTRATIONS_FILE = "chrome_registrations.conf"

REGISTRATIONS = None


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


class RegisterChromeView(HomeAssistantView):
    """Accepts push registrations from Chrome."""

    url = "/api/chrome/register"
    name = "api:chrome/register"

    def __init__(self, hass):
        """Init RegisterChromeView."""
        super().__init__(hass)

    def post(self, request):
        """Accept the POST request for push registrations from Chrome."""
        REGISTRATIONS[request.json['name']] = request.json['subscription']
        if not config_from_file(self.hass.config.path(REGISTRATIONS_FILE),
                                REGISTRATIONS):
            _LOGGER.error("failed to save config file")
        return self.json({"status": "ok"})


class ChromePushJavascriptView(HomeAssistantView):
    """Serves a small bit of Javascript that displays notifications."""

    requires_auth = False
    url = "/push.js"
    name = "pushjs"

    def __init__(self, hass):
        """Init ChromePushJavascriptView."""
        super().__init__(hass)

    def get(self, request):
        """Handle the GET request for the Javascript."""
        javascript = ('self.addEventListener("install",function(a){'
                      'self.skipWaiting()}),self.addEventListener("push",'
                      'function(a){a.data&&(data=a.data.json(),a.waitUntil('
                      'self.registration.showNotification(data.title,data'
                      ')))});')
        return self.Response(javascript, mimetype='text/javascript')


def get_service(hass, config):
    """Get the Chrome push notification service."""
    global REGISTRATIONS

    REGISTRATIONS = config_from_file(hass.config.path(REGISTRATIONS_FILE))

    hass.wsgi.register_view(RegisterChromeView(hass))
    hass.wsgi.register_view(ChromePushJavascriptView(hass))
    return ChromeNotificationService(hass, config.get('api_key'))


# pylint: disable=too-few-public-methods
class ChromeNotificationService(BaseNotificationService):
    """Implement the notification service for Chrome."""

    # pylint: disable=too-many-arguments
    def __init__(self, hass, api_key):
        """Initialize the service."""
        self.hass = hass
        self._api_key = api_key

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pywebpush import WebPusher
        payload = {"body": message}
        payload.update(dict((k, v) for k, v in kwargs.items() if v))
        if kwargs.get('icon') is None:
            payload['icon'] = '/static/icons/favicon-192x192.png'

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            _LOGGER.info("At least 1 target is required")
            return

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            if not REGISTRATIONS[target]:
                _LOGGER.error("%s is not a valid Chrome target!", target)
                return
            WebPusher(REGISTRATIONS[target]).send(json.dumps(payload),
                                                  gcm_key=self._api_key)
