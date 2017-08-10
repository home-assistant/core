"""
HipChat platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.hipchat/
"""
import logging
import json
import requests

import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TARGET, ATTR_DATA,
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import (
    CONF_TOKEN)
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = []

_LOGGER = logging.getLogger(__name__)

CONF_COLOR = 'color'
CONF_ROOM = 'room'
CONF_NOTIFY = 'notify'
CONF_FORMAT = 'format'
CONF_HOST = 'host'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_ROOM): cv.string,
    vol.Optional(CONF_COLOR, default='yellow'): cv.string,
    vol.Optional(CONF_NOTIFY, default=False): cv.boolean,
    vol.Optional(CONF_FORMAT, default='text'): cv.string,
    vol.Optional(CONF_HOST, default='api.hipchat.com'): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the HipChat notification service."""
    try:
        return HipchatNotificationService(
            config[CONF_TOKEN],
            config[CONF_ROOM],
            config[CONF_COLOR],
            config[CONF_NOTIFY],
            config[CONF_FORMAT],
            config[CONF_HOST])

    except requests.HTTPError as err:
        _LOGGER.exception(err.args)
        return None


class HipchatNotificationService(BaseNotificationService):
    """Implement the notification service for HipChat."""

    _valid_colors = {'yellow', 'green', 'red', 'purple', 'gray', 'random'}
    _valid_formats = {'text', 'html'}

    def __init__(self, token, default_room, default_color, default_notify,
                 default_format, host):
        """Initialize the service."""
        self._token = token
        self._default_room = default_room
        if default_color in self._valid_colors:
            self._default_color = default_color
        else:
            self._default_color = 'yellow'
        if isinstance(default_notify, bool):
            self._default_notify = default_notify
        else:
            self._default_notify = False
        self._default_format = default_format
        self._host = host

        self.auth_test()

    def auth_test(self):
        """Validate configuration."""
        self.send_message('Authentication Test', auth_test=True)

    def send_message(self, message="", **kwargs):
        """Send a message."""
        room = ''
        payload = {
            'message': message,
            'color': self._default_color,
            'notify': self._default_notify,
            'format': self._default_format,
            }
        auth_test = False

        if kwargs.get(ATTR_DATA) is not None:
            data = kwargs.get(ATTR_DATA)
            if ((data.get(CONF_COLOR) is not None)
                    and (data.get(CONF_COLOR) in self._valid_colors)):
                payload['color'] = data.get(CONF_COLOR)
            if ((data.get(CONF_NOTIFY) is not None)
                    and isinstance(data.get(CONF_NOTIFY), bool)):
                payload['notify'] = data.get(CONF_NOTIFY)
            if ((data.get(CONF_FORMAT) is not None)
                    and (data.get(CONF_FORMAT) in self._valid_formats)):
                payload['message_format'] = data.get(CONF_FORMAT)

        if kwargs.get(ATTR_TARGET) is None:
            targets = [self._default_room]
        else:
            targets = kwargs.get(ATTR_TARGET)

        if kwargs.get('auth_test') is not None:
            auth_test = kwargs.get('auth_test')

        for room in targets:

            url = "https://{0}/v2/room/{1}/notification".format(self._host,
                                                                room)
            if auth_test:
                url = url + '?auth_test=true'
            headers = {'Content-type': 'application/json'}
            headers['Authorization'] = "Bearer " + self._token
            req = requests.post(url, data=json.dumps(payload),
                                headers=headers)
            req.raise_for_status()
