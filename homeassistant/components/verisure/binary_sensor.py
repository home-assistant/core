"""Support for Verisure binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorEntity,
)

from . import CONF_DOOR_WINDOW, HUB as hub

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure binary sensors."""
    sensors = []
    hub.update_overview()

    if int(hub.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend(
            [
                VerisureDoorWindowSensor(device_label)
                for device_label in hub.get(
                    "$.doorWindow.doorWindowDevice[*].deviceLabel"
                )
            ]
        )

    sensors.extend([VerisureEthernetStatus()])
    add_entities(sensors)


class VerisureDoorWindowSensor(BinarySensorEntity):
    """Representation of a Verisure door window sensor."""

    def __init__(self, device_label):
        """Initialize the Verisure door window sensor."""
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].area",
            self._device_label,
        )

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].state",
                self._device_label,
            )
            == "OPEN"
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')]",
                self._device_label,
            )
            is not None
        )

    # pylint: disable=no-self-use
    def update(self):
        """Update the state of the sensor."""
        hub.update_overview()


class VerisureEthernetStatus(BinarySensorEntity):
    """Representation of a Verisure VBOX internet status."""

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "Verisure Ethernet status"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return hub.get_first("$.ethernetConnectedNow")

    @property
    def available(self):
        """Return True if entity is available."""
        return hub.get_first("$.ethernetConnectedNow") is not None

    # pylint: disable=no-self-use
    def update(self):
        """Update the state of the sensor."""
        hub.update_overview()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY
