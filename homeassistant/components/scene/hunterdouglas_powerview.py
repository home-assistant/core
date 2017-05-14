"""
Support for Powerview scenes from a Powerview hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene.hunterdouglas_powerview/
"""
import logging

from homeassistant.components.scene import Scene, DOMAIN
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import generate_entity_id
import asyncio

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = ['aiopvapi==1.1']

HUB_ADDRESS = 'address'

@asyncio.coroutine
def async_setup_platform(hass, config, async_add_devices, discovery_info=None):
    """Set up home assistant scene entries."""
    from aiopvapi.hub import Hub

    hub_address = config.get(HUB_ADDRESS)
    websession = async_get_clientsession(hass)


    _hub = Hub(hub_address,hass.loop,websession)
    _scenes = _hub.scenes.get_scenes()
    _rooms = _hub.rooms.get_rooms()

    if _scenes and _rooms:
        async_add_devices(PowerViewScene(hass, _scene, _rooms, _hub)
                for _scene in _scenes['sceneData'])
        return True
    else:
        return False

# pylint: disable=unused-argument
# def setup_platform(hass, config, add_devices, discovery_info=None):
#     """Set up the powerview scenes stored in a Powerview hub."""
#     from powerview_api import powerview
#
#     hub_address = config.get(HUB_ADDRESS)
#
#     _pv = powerview.PowerView(hub_address)
#     try:
#         _scenes = _pv.get_scenes()
#         _rooms = _pv.get_rooms()
#     except ConnectionError:
#         _LOGGER.exception("Error connecting to powerview "
#                           "hub with ip address: %s", hub_address)
#         return False
#     add_devices(PowerViewScene(hass, scene, _rooms, _pv)
#                 for scene in _scenes['sceneData'])
#
#     return True


class PowerViewScene(Scene):
    """Representation of a Powerview scene."""

    def __init__(self, hass, scene_data, room_data, hub):
        """Initialize the scene."""
        self.hub = hub
        self.hass = hass
        self.scene_data = scene_data
        self._sync_room_data(room_data)
        self.entity_id_format = DOMAIN + '.{}'
        self.entity_id = generate_entity_id(
            self.entity_id_format, str(self.scene_data["id"]), hass=hass)

    def _sync_room_data(self, room_data):
        """Sync the room data."""
        room = next((room for room in room_data["roomData"]
                     if room["id"] == self.scene_data["roomId"]), None)
        if room is not None:
            self.scene_data["roomName"] = room["name"]

    @property
    def name(self):
        """Return the name of the scene."""
        return str(self.scene_data["name"])

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {"roomName": self.scene_data["roomName"]}

    @property
    def icon(self):
        """Icon to use in the frontend."""
        return 'mdi:blinds'

    def async_activate(self):
        """Activate scene. Try to get entities into requested state.

        This method must be run in the event loop and returns a coroutine.
        """
        yield from self.hub.scenes.activate_scene(self.scene_data["id"])

