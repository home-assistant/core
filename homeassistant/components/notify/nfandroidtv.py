"""
Notifications for Android TV notification service.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.nfandroidtv/
"""
import os
import logging

import requests
import voluptuous as vol

from homeassistant.components.notify import (
    ATTR_TITLE, ATTR_TITLE_DEFAULT, ATTR_DATA, BaseNotificationService,
    PLATFORM_SCHEMA)
from homeassistant.const import CONF_TIMEOUT, CONF_ICON
import homeassistant.helpers.config_validation as cv

_LOGGER = logging.getLogger(__name__)

CONF_IP = 'host'
CONF_DURATION = 'duration'
CONF_POSITION = 'position'
CONF_TRANSPARENCY = 'transparency'
CONF_COLOR = 'color'
CONF_INTERRUPT = 'interrupt'

DEFAULT_DURATION = 5
DEFAULT_POSITION = 'bottom-right'
DEFAULT_TRANSPARENCY = 'default'
DEFAULT_COLOR = 'grey'
DEFAULT_INTERRUPT = False
DEFAULT_TIMEOUT = 5
DEFAULT_ICON = None

ATTR_DURATION = 'duration'
ATTR_POSITION = 'position'
ATTR_TRANSPARENCY = 'transparency'
ATTR_COLOR = 'color'
ATTR_BKGCOLOR = 'bkgcolor'
ATTR_INTERRUPT = 'interrupt'
ATTR_ICON = 'icon'
ATTR_FILENAME = 'filename'

POSITIONS = {
    'bottom-right': 0,
    'bottom-left': 1,
    'top-right': 2,
    'top-left': 3,
    'center': 4,
}

TRANSPARENCIES = {
    'default': 0,
    '0%': 1,
    '25%': 2,
    '50%': 3,
    '75%': 4,
    '100%': 5,
}

COLORS = {
    'grey': '#607d8b',
    'black': '#000000',
    'indigo': '#303F9F',
    'green': '#4CAF50',
    'red': '#F44336',
    'cyan': '#00BCD4',
    'teal': '#009688',
    'amber': '#FFC107',
    'pink': '#E91E63',
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_IP): cv.string,
    vol.Optional(CONF_DURATION, default=DEFAULT_DURATION): vol.Coerce(int),
    vol.Optional(CONF_POSITION, default=DEFAULT_POSITION):
        vol.In(POSITIONS.keys()),
    vol.Optional(CONF_TRANSPARENCY, default=DEFAULT_TRANSPARENCY):
        vol.In(TRANSPARENCIES.keys()),
    vol.Optional(CONF_COLOR, default=DEFAULT_COLOR):
        vol.In(COLORS.keys()),
    vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): vol.Coerce(int),
    vol.Optional(CONF_INTERRUPT, default=DEFAULT_INTERRUPT): cv.boolean,
    vol.Optional(CONF_ICON, default=DEFAULT_ICON): cv.string,
})


# pylint: disable=unused-argument
def get_service(hass, config, discovery_info=None):
    """Get the Notifications for Android TV notification service."""
    remoteip = config.get(CONF_IP)
    duration = config.get(CONF_DURATION)
    position = config.get(CONF_POSITION)
    transparency = config.get(CONF_TRANSPARENCY)
    color = config.get(CONF_COLOR)
    interrupt = config.get(CONF_INTERRUPT)
    timeout = config.get(CONF_TIMEOUT)
    icon = config.get(CONF_ICON)

    return NFAndroidTVNotificationService(
        remoteip, duration, position, transparency, color, interrupt, timeout,
        icon)


class NFAndroidTVNotificationService(BaseNotificationService):
    """Notification service for Notifications for Android TV."""

    def __init__(self, remoteip, duration, position, transparency, color,
                 interrupt, timeout, icon):
        """Initialize the service."""
        self._target = 'http://{}:7676'.format(remoteip)
        self._default_duration = duration
        self._default_position = position
        self._default_transparency = transparency
        self._default_color = color
        self._default_interrupt = interrupt
        self._timeout = timeout
        self._icon_file = None
        if icon:
            self._icon_file = icon
        else:
            try:
                import hass_frontend
                default_icon = os.path.join(
                    hass_frontend.__path__[0], 'icons', 'favicon-192x192.png')
                if os.path.exists(default_icon):
                    self._icon_file = default_icon
            except ImportError:
                _LOGGER.warning(
                    "hass_frontend icon not found. " + \
                    "Provide an icon when calling the service.")

    def send_message(self, message="", **kwargs):
        """Send a message to a Android TV device."""
        _LOGGER.debug("Sending notification to: %s", self._target)

        payload = dict(title=kwargs.get(ATTR_TITLE, ATTR_TITLE_DEFAULT),
                       msg=message, duration="%i" % self._default_duration,
                       position='%i' % POSITIONS.get(self._default_position),
                       bkgcolor='%s' % COLORS.get(self._default_color),
                       transparency='%i' % TRANSPARENCIES.get(
                           self._default_transparency),
                       offset='0', app=ATTR_TITLE_DEFAULT, force='true',
                       interrupt='%i' % self._default_interrupt)

        icon_file = None
        data = kwargs.get(ATTR_DATA)
        if data:
            if ATTR_ICON in data:
                icon_file = data.get(ATTR_ICON)
            if ATTR_DURATION in data:
                duration = data.get(ATTR_DURATION)
                try:
                    payload[ATTR_DURATION] = '%i' % int(duration)
                except ValueError:
                    _LOGGER.warning("Invalid duration-value: %s",
                                    str(duration))
            if ATTR_POSITION in data:
                position = data.get(ATTR_POSITION)
                if position in POSITIONS:
                    payload[ATTR_POSITION] = '%i' % POSITIONS.get(position)
                else:
                    _LOGGER.warning("Invalid position-value: %s",
                                    str(position))
            if ATTR_TRANSPARENCY in data:
                transparency = data.get(ATTR_TRANSPARENCY)
                if transparency in TRANSPARENCIES:
                    payload[ATTR_TRANSPARENCY] = '%i' % TRANSPARENCIES.get(
                        transparency)
                else:
                    _LOGGER.warning("Invalid transparency-value: %s",
                                    str(transparency))
            if ATTR_COLOR in data:
                color = data.get(ATTR_COLOR)
                if color in COLORS:
                    payload[ATTR_BKGCOLOR] = '%s' % COLORS.get(color)
                else:
                    _LOGGER.warning("Invalid color-value: %s", str(color))
            if ATTR_INTERRUPT in data:
                interrupt = data.get(ATTR_INTERRUPT)
                try:
                    payload[ATTR_INTERRUPT] = '%i' % cv.boolean(interrupt)
                except vol.Invalid:
                    _LOGGER.warning("Invalid interrupt-value: %s",
                                    str(interrupt))

        if self._icon_file is None and icon_file is None:
            _LOGGER.error("No icon available. Not sending notification.")
            return
        if icon_file is None:
            icon_file = self._icon_file
        payload[ATTR_FILENAME] = ('icon.png',
                                  open(icon_file, 'rb'),
                                  'application/octet-stream',
                                  {'Expires': '0'})

        try:
            _LOGGER.debug("Payload: %s", str(payload))
            response = requests.post(
                self._target, files=payload, timeout=self._timeout)
            if response.status_code != 200:
                _LOGGER.error("Error sending message: %s", str(response))
        except requests.exceptions.ConnectionError as err:
            _LOGGER.error("Error communicating with %s: %s",
                          self._target, str(err))
