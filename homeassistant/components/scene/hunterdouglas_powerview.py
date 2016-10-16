"""
Support for Powerview scenes from a Powerview hub.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/scene.hunterdouglas_powerview/
"""
import logging

from homeassistant.components.scene import Scene, DOMAIN
from homeassistant.helpers.entity import generate_entity_id

_LOGGER = logging.getLogger(__name__)
REQUIREMENTS = [
    'https://github.com/sander76/powerviewApi/'
    'archive/cc6f75dd39160d4aaf46cb2ed9220136b924bcb4.zip#powerviewApi==0.2']

HUB_ADDRESS = 'address'


# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the powerview scenes stored in a Powerview hub."""
    import powerview

    hub_address = config.get(HUB_ADDRESS)

    _pv = powerview.PowerView(hub_address)
    try:
        _scenes = _pv.get_scenes()
        _rooms = _pv.get_rooms()
    except ConnectionError:
        _LOGGER.exception("error connecting to powerview "
                          "hub with ip address: %s", hub_address)
        return False
    add_devices(PowerViewScene(hass, scene, _rooms, _pv)
                for scene in _scenes['sceneData'])

    return True


class PowerViewScene(Scene):
    """Representation of a Powerview scene."""

    def __init__(self, hass, scene_data, room_data, pv_instance):
        """Initialize the scene."""
        self.pv_instance = pv_instance
        self.hass = hass
        self.scene_data = scene_data
        self._sync_room_data(room_data)
        self.entity_id_format = DOMAIN + '.{}'
        self.entity_id = generate_entity_id(self.entity_id_format,
                                            str(self.scene_data["id"]),
                                            hass=hass)

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

    def activate(self):
        """Activate the scene. Tries to get entities into requested state."""
        self.pv_instance.activate_scene(self.scene_data["id"])
