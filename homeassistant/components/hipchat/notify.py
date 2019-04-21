"""
HipChat platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.hipchat/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_HOST, CONF_ROOM, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (ATTR_DATA, ATTR_TARGET,
                                             PLATFORM_SCHEMA,
                                             BaseNotificationService)

REQUIREMENTS = ['hipnotify==1.0.8']

_LOGGER = logging.getLogger(__name__)

CONF_COLOR = 'color'
CONF_NOTIFY = 'notify'
CONF_FORMAT = 'format'

DEFAULT_COLOR = 'yellow'
DEFAULT_FORMAT = 'text'
DEFAULT_HOST = 'https://api.hipchat.com/'
DEFAULT_NOTIFY = False

VALID_COLORS = {'yellow', 'green', 'red', 'purple', 'gray', 'random'}
VALID_FORMATS = {'text', 'html'}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ROOM): vol.Coerce(int),
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_COLOR, default=DEFAULT_COLOR): vol.In(VALID_COLORS),
    vol.Optional(CONF_FORMAT, default=DEFAULT_FORMAT): vol.In(VALID_FORMATS),
    vol.Optional(CONF_HOST, default=DEFAULT_HOST): cv.string,
    vol.Optional(CONF_NOTIFY, default=DEFAULT_NOTIFY): cv.boolean,
})


def get_service(hass, config, discovery_info=None):
    """Get the HipChat notification service."""
    return HipchatNotificationService(
        config[CONF_TOKEN], config[CONF_ROOM], config[CONF_COLOR],
        config[CONF_NOTIFY], config[CONF_FORMAT], config[CONF_HOST])


class HipchatNotificationService(BaseNotificationService):
    """Implement the notification service for HipChat."""

    def __init__(self, token, default_room, default_color, default_notify,
                 default_format, host):
        """Initialize the service."""
        self._token = token
        self._default_room = default_room
        self._default_color = default_color
        self._default_notify = default_notify
        self._default_format = default_format
        self._host = host

        self._rooms = {}
        self._get_room(self._default_room)

    def _get_room(self, room):
        """Get Room object, creating it if necessary."""
        from hipnotify import Room
        if room not in self._rooms:
            self._rooms[room] = Room(
                token=self._token, room_id=room, endpoint_url=self._host)
        return self._rooms[room]

    def send_message(self, message="", **kwargs):
        """Send a message."""
        color = self._default_color
        notify = self._default_notify
        message_format = self._default_format

        if kwargs.get(ATTR_DATA) is not None:
            data = kwargs.get(ATTR_DATA)
            if ((data.get(CONF_COLOR) is not None)
                    and (data.get(CONF_COLOR) in VALID_COLORS)):
                color = data.get(CONF_COLOR)
            if ((data.get(CONF_NOTIFY) is not None)
                    and isinstance(data.get(CONF_NOTIFY), bool)):
                notify = data.get(CONF_NOTIFY)
            if ((data.get(CONF_FORMAT) is not None)
                    and (data.get(CONF_FORMAT) in VALID_FORMATS)):
                message_format = data.get(CONF_FORMAT)

        targets = kwargs.get(ATTR_TARGET, [self._default_room])

        for target in targets:
            room = self._get_room(target)
            room.notify(msg=message, color=color, notify=notify,
                        message_format=message_format)
