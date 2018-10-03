"""
Support for Powerview scenes from a Powerview hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene.hunterdouglas_powerview/
"""
import logging

import voluptuous as vol

from homeassistant.components.scene import Scene, DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import async_generate_entity_id

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['aiopvapi==1.5.4']

ENTITY_ID_FORMAT = DOMAIN + '.{}'
HUB_ADDRESS = 'address'

PLATFORM_SCHEMA = vol.Schema({
    vol.Required(CONF_PLATFORM): 'hunterdouglas_powerview',
    vol.Required(HUB_ADDRESS): cv.string,
})

SCENE_DATA = 'sceneData'
ROOM_DATA = 'roomData'
SCENE_NAME = 'name'
ROOM_NAME = 'name'
SCENE_ID = 'id'
ROOM_ID = 'id'
ROOM_ID_IN_SCENE = 'roomId'
STATE_ATTRIBUTE_ROOM_NAME = 'roomName'


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up home assistant scene entries."""
    # from aiopvapi.hub import Hub
    from aiopvapi.scenes import Scenes
    from aiopvapi.rooms import Rooms
    from aiopvapi.resources.scene import Scene as PvScene

    hub_address = config.get(HUB_ADDRESS)
    websession = async_get_clientsession(hass)

    _scenes = await Scenes(
        hub_address, hass.loop, websession).get_resources()
    _rooms = await Rooms(
        hub_address, hass.loop, websession).get_resources()

    if not _scenes or not _rooms:
        _LOGGER.error(
            "Unable to initialize PowerView hub: %s", hub_address)
        return
    pvscenes = (PowerViewScene(hass,
                               PvScene(_raw_scene, hub_address, hass.loop,
                                       websession), _rooms)
                for _raw_scene in _scenes[SCENE_DATA])
    async_add_entities(pvscenes)


class PowerViewScene(Scene):
    """Representation of a Powerview scene."""

    def __init__(self, hass, scene, room_data):
        """Initialize the scene."""
        self._scene = scene
        self.hass = hass
        self._room_name = None
        self._sync_room_data(room_data)
        self.entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, str(self._scene.id), hass=hass)

    def _sync_room_data(self, room_data):
        """Sync room data."""
        room = next((room for room in room_data[ROOM_DATA]
                     if room[ROOM_ID] == self._scene.room_id), {})

        self._room_name = room.get(ROOM_NAME, '')

    @property
    def name(self):
        """Return the name of the scene."""
        return self._scene.name

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {STATE_ATTRIBUTE_ROOM_NAME: self._room_name}

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:blinds'

    def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        yield from self._scene.activate()
