"""Support for August sensors."""
from datetime import timedelta
import logging
import random

from homeassistant.components.sensor import DEVICE_CLASS_POWER
from homeassistant.const import POWER_WATT
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=1)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the scaletest sensors."""

    entities = []

    for i in range(100):
        entities.append(ScaleTestSensor(f"power_sensor_{i}"))

    async_add_entities(entities, True)


class ScaleTestSensor(Entity):
    """Representation of an scaletest sensor."""

    def __init__(self, name):
        """Initialize the sensor."""
        self._name = name

    @property
    def available(self):
        """Return the availability of this sensor."""
        return True

    @property
    def state(self):
        """Return the state of the sensor."""
        return random.randint(0, 500000)

    @property
    def device_class(self):
        """Return the device class of the power sensor."""
        return DEVICE_CLASS_POWER

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return POWER_WATT

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def should_poll(self):
        """Return the device should not poll for updates."""
        return True
