"""
HTML5 Push Messaging notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.html5/
"""
import os
import logging
import json

from homeassistant.components.notify import (ATTR_TARGET,
                                             BaseNotificationService)
from homeassistant.components.http import HomeAssistantView

from homeassistant.components.frontend import add_manifest_json_key

REQUIREMENTS = ['https://github.com/web-push-libs/pywebpush/archive/'
                'e743dc92558fc62178d255c0018920d74fa778ed.zip#'
                'pywebpush==0.5.0']

DEPENDENCIES = ["http"]

_LOGGER = logging.getLogger(__name__)

REGISTRATIONS_FILE = "html5_push_registrations.conf"

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


class HTML5PushRegistrationView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    url = "/api/notify.html5"
    name = "api:notify.html5"

    def __init__(self, hass):
        """Init HTML5PushRegistrationView."""
        super().__init__(hass)

    def post(self, request):
        """Accept the POST request for push registrations from a browser."""
        REGISTRATIONS[request.json['name']] = request.json['subscription']
        if not config_from_file(self.hass.config.path(REGISTRATIONS_FILE),
                                REGISTRATIONS):
            _LOGGER.error("failed to save config file")
        return self.json({"status": "ok"})


def get_service(hass, config):
    """Get the HTML5 push notification service."""
    global REGISTRATIONS

    REGISTRATIONS = config_from_file(hass.config.path(REGISTRATIONS_FILE))

    hass.wsgi.register_view(HTML5PushRegistrationView(hass))

    if config.get('gcm_sender_id') is not None:
        add_manifest_json_key('gcm_sender_id', config.get('gcm_sender_id'))

    return HTML5NotificationService(config.get('gcm_api_key', None))


# pylint: disable=too-few-public-methods
class HTML5NotificationService(BaseNotificationService):
    """Implement the notification service for HTML5."""

    # pylint: disable=too-many-arguments
    def __init__(self, gcm_key):
        """Initialize the service."""
        self._gcm_key = gcm_key

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
            if REGISTRATIONS.get(target) is None:
                _LOGGER.error("%s is not a valid HTML5 push notification"
                              " target!", target)
                return
            WebPusher(REGISTRATIONS[target]).send(json.dumps(payload),
                                                  gcm_key=self._gcm_key)
