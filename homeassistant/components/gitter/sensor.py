"""Support for displaying details about a Gitter.im chat room."""

from __future__ import annotations

import logging

from gitterpy.client import GitterClient
from gitterpy.errors import GitterRoomError, GitterTokenError
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_API_KEY, CONF_NAME, CONF_ROOM
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_MENTION = "mention"
ATTR_ROOM = "room"
ATTR_USERNAME = "username"

DEFAULT_NAME = "Gitter messages"
DEFAULT_ROOM = "home-assistant/home-assistant"


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_API_KEY): cv.string,
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROOM, default=DEFAULT_ROOM): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Gitter sensor."""

    name = config.get(CONF_NAME)
    api_key = config.get(CONF_API_KEY)
    room = config.get(CONF_ROOM)

    gitter = GitterClient(api_key)
    try:
        username = gitter.auth.get_my_id["name"]
    except GitterTokenError:
        _LOGGER.error("Token is not valid")
        return

    add_entities([GitterSensor(gitter, room, name, username)], True)


class GitterSensor(SensorEntity):
    """Representation of a Gitter sensor."""

    _attr_icon = "mdi:message-cog"

    def __init__(self, data, room, name, username):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._room = room
        self._username = username
        self._state = None
        self._mention = 0
        self._unit_of_measurement = "Msg"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self._unit_of_measurement

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_USERNAME: self._username,
            ATTR_ROOM: self._room,
            ATTR_MENTION: self._mention,
        }

    def update(self) -> None:
        """Get the latest data and updates the state."""

        try:
            data = self._data.user.unread_items(self._room)
        except GitterRoomError as error:
            _LOGGER.error(error)
            return

        if "error" not in data:
            self._mention = len(data["mention"])
            self._state = len(data["chat"])
        else:
            _LOGGER.error("Not joined: %s", self._room)
