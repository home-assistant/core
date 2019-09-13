"""Support for VersaSense sensor peripheral."""
import logging

from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    consumer = hass.data[DOMAIN]["consumer"]

    for entity_info in discovery_info:
        parent_name = entity_info["parent_name"]
        peripheral = hass.data[DOMAIN][entity_info["identifier"]]
        unit = entity_info["unit"]
        measurement = entity_info["measurement"]

        async_add_entities(
            [VSensor(peripheral, parent_name, unit, measurement, consumer)]
        )


class VSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, peripheral, parent_name, unit, measurement, consumer):
        """Initialize the sensor."""
        self._state = None
        self._available = True
        self._name = "{} {}".format(parent_name, measurement)
        self._parent_mac = peripheral.parentMac
        self._identifier = peripheral.identifier
        self._unit = unit
        self._measurement = measurement
        self.consumer = consumer

    @property
    def unique_id(self):
        """Return the unique id of the sensor."""
        return f"{self._parent_mac}/{self._identifier}/{self._measurement}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    @property
    def available(self):
        """Return if the sensor is available."""
        return self._available

    async def async_update(self):
        """Fetch new state data for the sensor."""
        samples = await self.consumer.fetchPeripheralSample(
            None, self._identifier, self._parent_mac
        )

        if samples is not None:
            for sample in samples:
                if sample.measurement == self._measurement:
                    self._available = True
                    self._state = sample.value
        else:
            _LOGGER.error("Sample unavailable")
            self._available = False
            self._state = None
