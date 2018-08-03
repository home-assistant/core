"""
Interfaces with Verisure sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/binary_sensor.verisure/
"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.components.verisure import CONF_DOOR_WINDOW
from homeassistant.components.verisure import HUB as hub

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Verisure binary sensors."""
    sensors = []
    hub.update_overview()

    if int(hub.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend([
            VerisureDoorWindowSensor(device_label)
            for device_label in hub.get(
                "$.doorWindow.doorWindowDevice[*].deviceLabel")])
    add_devices(sensors)


class VerisureDoorWindowSensor(BinarySensorDevice):
    """Representation of a Verisure door window sensor."""

    def __init__(self, device_label):
        """Initialize the Verisure door window sensor."""
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].area",
            self._device_label)

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].state",
            self._device_label) == "OPEN"

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')]",
            self._device_label) is not None

    # pylint: disable=no-self-use
    def update(self):
        """Update the state of the sensor."""
        hub.update_overview()
