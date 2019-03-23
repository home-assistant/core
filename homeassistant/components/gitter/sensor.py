"""
Support for displaying details about a Gitter.im chat room.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.gitter/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_ROOM
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['gitterpy==0.1.7']

_LOGGER = logging.getLogger(__name__)

ATTR_MENTION = 'mention'
ATTR_ROOM = 'room'
ATTR_USERNAME = 'username'

DEFAULT_NAME = 'Gitter messages'
DEFAULT_ROOM = 'home-assistant/home-assistant'

ICON = 'mdi:message-settings-variant'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_API_KEY): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_ROOM, default=DEFAULT_ROOM): cv.string,
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Gitter sensor."""
    from gitterpy.client import GitterClient
    from gitterpy.errors import GitterTokenError

    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    room = config.get(CONF_ROOM)

    gitter = GitterClient(api_key)
    try:
        username = gitter.auth.get_my_id['name']
    except GitterTokenError:
        _LOGGER.error("Token is not valid")
        return

    add_entities([GitterSensor(gitter, room, name, username)], True)


class GitterSensor(Entity):
    """Representation of a Gitter sensor."""

    def __init__(self, data, room, name, username):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._room = room
        self._username = username
        self._state = None
        self._mention = 0
        self._unit_of_measurement = 'Msg'

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_USERNAME: self._username,
            ATTR_ROOM: self._room,
            ATTR_MENTION: self._mention,
        }

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Get the latest data and updates the state."""
        from gitterpy.errors import GitterRoomError

        try:
            data = self._data.user.unread_items(self._room)
        except GitterRoomError as error:
            _LOGGER.error(error)
            return

        if 'error' not in data.keys():
            self._mention = len(data['mention'])
            self._state = len(data['chat'])
        else:
            _LOGGER.error("Not joined: %s", self._room)
