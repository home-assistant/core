"""
homeassistant.components.switch.child_light
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

"""

from homeassistant.components.switch.child_switch import ChildSwitch
from homeassistant.components.light import (
	Light, ATTR_BRIGHTNESS)

# pylint: disable=unused-argument
def setup_platform(hass, config, add_devices, discovery_info=None):
    """ Sets up the sensors. """
    dev = []
    child_light = ChildLight(config, discovery_info)
    dev.append(child_light)

    add_devices(dev)

    hass.states.track_change(
        discovery_info.get('parent_entity_id'), child_light.track_state)

class ChildLight(Light, ChildSwitch):
    pass