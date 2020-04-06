"""Support for Verisure binary sensors."""
import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    BinarySensorDevice,
)

from . import CONF_DOOR_WINDOW, DOMAIN

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure binary sensors."""
    hub = hass.data[DOMAIN]
    sensors = []
    hub.update_overview()

    if int(hub.config.get(CONF_DOOR_WINDOW, 1)):
        sensors.extend(
            [
                VerisureDoorWindowSensor(hub, device_label)
                for device_label in hub.get(
                    "$.doorWindow.doorWindowDevice[*].deviceLabel"
                )
            ]
        )

    sensors.extend([VerisureEthernetStatus(hub)])
    add_entities(sensors)


class VerisureDoorWindowSensor(BinarySensorDevice):
    """Representation of a Verisure door window sensor."""

    def __init__(self, hub, device_label):
        """Initialize the Verisure door window sensor."""
        self._hub = hub
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._hub.get_first(
            "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].area",
            self._device_label,
        )

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return (
            self._hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')].state",
                self._device_label,
            )
            == "OPEN"
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            self._hub.get_first(
                "$.doorWindow.doorWindowDevice[?(@.deviceLabel=='%s')]",
                self._device_label,
            )
            is not None
        )

    # pylint: disable=no-self-use
    def update(self):
        """Update the state of the sensor."""
        self._hub.update_overview()


class VerisureEthernetStatus(BinarySensorDevice):
    """Representation of a Verisure VBOX internet status."""

    def __init__(self, hub):
        """Initialize the Verisure ethernet status sensor."""
        self._hub = hub

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return "Verisure Ethernet status"

    @property
    def is_on(self):
        """Return the state of the sensor."""
        return self._hub.get_first("$.ethernetConnectedNow")

    @property
    def available(self):
        """Return True if entity is available."""
        return self._hub.get_first("$.ethernetConnectedNow") is not None

    # pylint: disable=no-self-use
    def update(self):
        """Update the state of the sensor."""
        self._hub.update_overview()

    @property
    def device_class(self):
        """Return the class of this device, from component DEVICE_CLASSES."""
        return DEVICE_CLASS_CONNECTIVITY
