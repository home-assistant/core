"""Support for Verisure sensors."""
import logging

from homeassistant.const import PERCENTAGE, TEMP_CELSIUS
from homeassistant.helpers.entity import Entity

from . import CONF_HYDROMETERS, CONF_MOUSE, CONF_THERMOMETERS, HUB as hub

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Verisure platform."""
    sensors = []
    hub.update_overview()

    if int(hub.config.get(CONF_THERMOMETERS, 1)):
        sensors.extend(
            [
                VerisureThermometer(device_label)
                for device_label in hub.get(
                    "$.climateValues[?(@.temperature)].deviceLabel"
                )
            ]
        )

    if int(hub.config.get(CONF_HYDROMETERS, 1)):
        sensors.extend(
            [
                VerisureHygrometer(device_label)
                for device_label in hub.get(
                    "$.climateValues[?(@.humidity)].deviceLabel"
                )
            ]
        )

    if int(hub.config.get(CONF_MOUSE, 1)):
        sensors.extend(
            [
                VerisureMouseDetection(device_label)
                for device_label in hub.get(
                    "$.eventCounts[?(@.deviceType=='MOUSE1')].deviceLabel"
                )
            ]
        )

    add_entities(sensors)


class VerisureThermometer(Entity):
    """Representation of a Verisure thermometer."""

    def __init__(self, device_label):
        """Initialize the sensor."""
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the device."""
        return (
            hub.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].deviceArea", self._device_label
            )
            + " temperature"
        )

    @property
    def state(self):
        """Return the state of the device."""
        return hub.get_first(
            "$.climateValues[?(@.deviceLabel=='%s')].temperature", self._device_label
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            hub.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].temperature",
                self._device_label,
            )
            is not None
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return TEMP_CELSIUS

    # pylint: disable=no-self-use
    def update(self):
        """Update the sensor."""
        hub.update_overview()


class VerisureHygrometer(Entity):
    """Representation of a Verisure hygrometer."""

    def __init__(self, device_label):
        """Initialize the sensor."""
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the device."""
        return (
            hub.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].deviceArea", self._device_label
            )
            + " humidity"
        )

    @property
    def state(self):
        """Return the state of the device."""
        return hub.get_first(
            "$.climateValues[?(@.deviceLabel=='%s')].humidity", self._device_label
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            hub.get_first(
                "$.climateValues[?(@.deviceLabel=='%s')].humidity", self._device_label
            )
            is not None
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return PERCENTAGE

    # pylint: disable=no-self-use
    def update(self):
        """Update the sensor."""
        hub.update_overview()


class VerisureMouseDetection(Entity):
    """Representation of a Verisure mouse detector."""

    def __init__(self, device_label):
        """Initialize the sensor."""
        self._device_label = device_label

    @property
    def name(self):
        """Return the name of the device."""
        return (
            hub.get_first(
                "$.eventCounts[?(@.deviceLabel=='%s')].area", self._device_label
            )
            + " mouse"
        )

    @property
    def state(self):
        """Return the state of the device."""
        return hub.get_first(
            "$.eventCounts[?(@.deviceLabel=='%s')].detections", self._device_label
        )

    @property
    def available(self):
        """Return True if entity is available."""
        return (
            hub.get_first("$.eventCounts[?(@.deviceLabel=='%s')]", self._device_label)
            is not None
        )

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity."""
        return "Mice"

    # pylint: disable=no-self-use
    def update(self):
        """Update the sensor."""
        hub.update_overview()
