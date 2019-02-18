"""Support for Powerview scenes from a Powerview hub."""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.scene import Scene, DOMAIN
from homeassistant.const import CONF_PLATFORM
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import async_generate_entity_id

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['aiopvapi==1.6.14']

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
    from aiopvapi.helpers.aiorequest import AioRequest
    from aiopvapi.scenes import Scenes
    from aiopvapi.rooms import Rooms
    from aiopvapi.resources.scene import Scene as PvScene

    hub_address = config.get(HUB_ADDRESS)
    websession = async_get_clientsession(hass)

    pv_request = AioRequest(hub_address, loop=hass.loop, websession=websession)

    _scenes = await Scenes(pv_request).get_resources()
    _rooms = await Rooms(pv_request).get_resources()

    if not _scenes or not _rooms:
        _LOGGER.error(
            "Unable to initialize PowerView hub: %s", hub_address)
        return
    pvscenes = (PowerViewScene(hass,
                               PvScene(_raw_scene, pv_request), _rooms)
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

    async def async_activate(self):
        """Activate scene. Try to get entities into requested state."""
        await self._scene.activate()
