"""
Stride platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.stride/
"""
import logging

import voluptuous as vol

from homeassistant.const import CONF_ROOM, CONF_TOKEN
import homeassistant.helpers.config_validation as cv

from homeassistant.components.notify import (ATTR_DATA, ATTR_TARGET,
                                             PLATFORM_SCHEMA,
                                             BaseNotificationService)

REQUIREMENTS = ['pystride==0.1.7']

_LOGGER = logging.getLogger(__name__)

CONF_PANEL = 'panel'
CONF_CLOUDID = 'cloudid'

DEFAULT_PANEL = None

VALID_PANELS = {'info', 'note', 'tip', 'warning', None}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLOUDID): cv.string,
    vol.Required(CONF_ROOM): cv.string,
    vol.Required(CONF_TOKEN): cv.string,
    vol.Optional(CONF_PANEL, default=DEFAULT_PANEL): vol.In(VALID_PANELS),
})


def get_service(hass, config, discovery_info=None):
    """Get the Stride notification service."""
    return StrideNotificationService(
        config[CONF_TOKEN], config[CONF_ROOM], config[CONF_PANEL],
        config[CONF_CLOUDID])


class StrideNotificationService(BaseNotificationService):
    """Implement the notification service for Stride."""

    def __init__(self, token, default_room, default_panel, cloudid):
        """Initialize the service."""
        self._token = token
        self._default_room = default_room
        self._default_panel = default_panel
        self._cloudid = cloudid

        from stride import Stride
        self._stride = Stride(self._cloudid, access_token=self._token)

    def send_message(self, message="", **kwargs):
        """Send a message."""
        panel = self._default_panel

        if kwargs.get(ATTR_DATA) is not None:
            data = kwargs.get(ATTR_DATA)
            if ((data.get(CONF_PANEL) is not None)
                    and (data.get(CONF_PANEL) in VALID_PANELS)):
                panel = data.get(CONF_PANEL)

        message_text = {
            'type': 'paragraph',
            'content': [
                {
                    'type': 'text',
                    'text': message
                }
            ]
            }
        panel_text = message_text
        if panel is not None:
            panel_text = {
                'type': 'panel',
                'attrs':
                    {
                        'panelType': panel
                    },
                'content':
                    [
                        message_text,
                    ]
                }

        message_doc = {
            'body': {
                'version': 1,
                'type': 'doc',
                'content':
                [
                    panel_text,
                ]
                }
            }

        targets = kwargs.get(ATTR_TARGET, [self._default_room])

        for target in targets:
            self._stride.message_room(target, message_doc)
