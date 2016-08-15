"""
HTML5 Push Messaging notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.html5/
"""
import os
import logging
import json
import time
import uuid

import voluptuous as vol
from voluptuous.humanize import humanize_error

from homeassistant.const import (
    HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, HTTP_UNAUTHORIZED)
from homeassistant.util import ensure_unique_string
from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_TITLE, ATTR_DATA, BaseNotificationService,
    PLATFORM_SCHEMA)
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.frontend import add_manifest_json_key
from homeassistant.helpers import config_validation as cv

REQUIREMENTS = ['https://github.com/web-push-libs/pywebpush/archive/'
                'e743dc92558fc62178d255c0018920d74fa778ed.zip#'
                'pywebpush==0.5.0']

DEPENDENCIES = ["frontend"]

_LOGGER = logging.getLogger(__name__)

REGISTRATIONS_FILE = "html5_push_registrations.conf"
TAGS_FILE = "html5_push_tags.conf"

ATTR_GCM_SENDER_ID = 'gcm_sender_id'
ATTR_GCM_API_KEY = 'gcm_api_key'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(ATTR_GCM_SENDER_ID): cv.string,
    vol.Optional(ATTR_GCM_API_KEY): cv.string,
})

ATTR_SUBSCRIPTION = 'subscription'
ATTR_BROWSER = 'browser'

REGISTER_SCHEMA = vol.Schema({
    vol.Required(ATTR_SUBSCRIPTION): cv.match_all,
    vol.Required(ATTR_BROWSER): vol.In(['chrome', 'firefox'])
})

NOTIFY_CALLBACK_EVENT = "html5_notification"


def get_service(hass, config):
    """Get the HTML5 push notification service."""
    json_path = hass.config.path(REGISTRATIONS_FILE)
    tags_path = hass.config.path(TAGS_FILE)

    registrations = _load_config(json_path)
    tags = _load_config(tags_path)

    if registrations is None:
        return None

    hass.wsgi.register_view(
        HTML5PushRegistrationView(hass, registrations, json_path))
    hass.wsgi.register_view(HTML5PushCallbackView(hass, tags_path))

    gcm_api_key = config.get('gcm_api_key')
    gcm_sender_id = config.get('gcm_sender_id')

    if gcm_sender_id is not None:
        add_manifest_json_key('gcm_sender_id', config.get('gcm_sender_id'))

    return HTML5NotificationService(gcm_api_key, registrations, tags,
                                    tags_path)


def _load_config(filename):
    """Load configuration."""
    if not os.path.isfile(filename):
        return {}

    try:
        with open(filename, "r") as fdesc:
            inp = fdesc.read()

        # In case empty file
        if not inp:
            return {}

        return json.loads(inp)
    except (IOError, ValueError) as error:
        _LOGGER.error("Reading config file %s failed: %s", filename, error)
        return None


def _save_config(filename, config):
    """Save configuration."""
    try:
        with open(filename, "w") as fdesc:
            fdesc.write(json.dumps(config, indent=4, sort_keys=True))
    except (IOError, TypeError) as error:
        _LOGGER.error("Saving config file failed: %s", error)
        return False
    return True


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

        if not _save_config(self.json_path, self.registrations):
            return self.json_message('Error saving registration.',
                                     HTTP_INTERNAL_SERVER_ERROR)

        return self.json_message("Push notification subscriber registered.")


class HTML5PushCallbackView(HomeAssistantView):
    """Accepts push registrations from a browser."""

    requires_auth = False
    url = "/api/notify.html5/callback"
    name = "api:notify.html5/callback"

    def __init__(self, hass, tags_path):
        """Init HTML5PushCallbackView."""
        super().__init__(hass)
        self.tags_path = tags_path

    def post(self, request):
        """Accept the POST request for push registrations event callback."""
        if request.json.get('tag') is None:
            return self.json_message("No tag provided!", HTTP_UNAUTHORIZED)
        tags = _load_config(self.tags_path)
        tag = request.json['tag']
        if tag in tags.keys():
            if tags[tag]['timestamp'] - int(time.time()) > 86400:
                msg = "{} is an expired tag!".format(tag)
                return self.json_message(msg, HTTP_UNAUTHORIZED)
            else:
                event_name = "{}.{}".format(NOTIFY_CALLBACK_EVENT,
                                            request.json['type'])
                event_payload = {"targets": tags[tag]['targets']}
                event_payload.update(request.json)
                self.hass.bus.fire(event_name, event_payload)
                return self.json({"status": "ok",
                                  "event": request.json['type']})
        else:
            msg = "{} is not a valid tag!".format(request.json['tag'])
            return self.json_message(msg, HTTP_UNAUTHORIZED)


# pylint: disable=too-few-public-methods
class HTML5NotificationService(BaseNotificationService):
    """Implement the notification service for HTML5."""

    # pylint: disable=too-many-arguments
    def __init__(self, gcm_key, registrations, tags, tags_path):
        """Initialize the service."""
        self._gcm_key = gcm_key
        self.registrations = registrations
        self.tags = tags
        self.tags_path = tags_path

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from pywebpush import WebPusher

        tag = str(uuid.uuid4())

        timestamp = int(time.time())

        payload = {
            'body': message,
            'data': {},
            'icon': '/static/icons/favicon-192x192.png',
            'tag': tag,
            'timestamp': (timestamp*1000),  # Javascript ms since epoch
            'title': kwargs.get(ATTR_TITLE)
        }

        data = kwargs.get(ATTR_DATA)

        if data:
            payload.update(data)
            payload['data'] = data

        if (payload['data'].get('url') is None and \
            payload['data'].get('actions') is None):
            payload['data']['url'] = '/'

        targets = kwargs.get(ATTR_TARGET)

        if not targets:
            targets = self.registrations.keys()
        elif not isinstance(targets, list):
            targets = [targets]

        self.tags[tag] = {"timestamp": timestamp, "targets": list(targets)}

        if not _save_config(self.tags_path, self.tags):
            _LOGGER.error("Error saving %s to the tags file!", tag)

        for target in targets:
            info = self.registrations.get(target)
            if info is None:
                _LOGGER.error("%s is not a valid HTML5 push notification"
                              " target!", target)
                continue

            WebPusher(info[ATTR_SUBSCRIPTION]).send(
                json.dumps(payload), gcm_key=self._gcm_key, ttl='86400')
