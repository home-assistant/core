"""Support for Lutron scenes."""
import logging

from homeassistant.components.scene import Scene

from . import LUTRON_CONTROLLER, LUTRON_DEVICES, LutronDevice

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['lutron']


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Lutron scenes."""
    devs = []
    for scene_data in hass.data[LUTRON_DEVICES]['scene']:
        (area_name, keypad_name, device, led) = scene_data
        dev = LutronScene(area_name, keypad_name, device, led,
                          hass.data[LUTRON_CONTROLLER])
        devs.append(dev)

    add_entities(devs, True)


class LutronScene(LutronDevice, Scene):
    """Representation of a Lutron Scene."""

    def __init__(
            self, area_name, keypad_name, lutron_device, lutron_led,
            controller):
        """Initialize the scene/button."""
        super().__init__(area_name, lutron_device, controller)
        self._keypad_name = keypad_name
        self._led = lutron_led

    def activate(self):
        """Activate the scene."""
        self._lutron_device.press()

    @property
    def name(self):
        """Return the name of the device."""
        return "{} {}: {}".format(
            self._area_name, self._keypad_name, self._lutron_device.name)
