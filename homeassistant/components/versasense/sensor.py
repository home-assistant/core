"""Support for VersaSense sensor peripheral."""
import logging

from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the sensor platform."""
    consumer = hass.data[DOMAIN]['consumer']
    peripheral = hass.data[DOMAIN][discovery_info['identifier']]
    parent_name = discovery_info['parentName']
    unit = discovery_info['unit']
    measurement = discovery_info['measurement']

    add_devices(
        [VSensor(peripheral, parent_name, unit, measurement, consumer)]
    )


class VSensor(Entity):
    """Representation of a Sensor."""

    def __init__(self, peripheral, parent_name, unit, measurement, consumer):
        """Initialize the sensor."""
        self._state = None
        self._name = parent_name + ": " + measurement
        self._parent_mac = peripheral.parentMac
        self._identifier = peripheral.identifier
        self._unit = unit
        self._measurement = measurement
        self.consumer = consumer

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def parent_mac(self):
        """Return the parent mac address of the sensor."""
        return self._parent_mac

    @property
    def identifier(self):
        """Return the identifier of the sensor."""
        return self._identifier

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit

    async def async_update(self):
        """Fetch new state data for the sensor."""
        samples = await self.consumer.fetchPeripheralSample(
            None, self.identifier, self._parent_mac
        )

        if samples is not None:
            for sample in samples:
                if sample.measurement == self._measurement:
                    self._state = sample.value
        else:
            _LOGGER.error("Sample unavailable")
            self._state = None
