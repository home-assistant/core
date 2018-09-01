"""
Support for IGD Sensors.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.igd/
"""
# pylint: disable=invalid-name
from datetime import datetime
import logging

from homeassistant.components.igd import DOMAIN
from homeassistant.helpers.entity import Entity


_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['igd', 'history']

BYTES_RECEIVED = 'bytes_received'
BYTES_SENT = 'bytes_sent'
PACKETS_RECEIVED = 'packets_received'
PACKETS_SENT = 'packets_sent'

SENSOR_TYPES = {
    BYTES_RECEIVED: {
        'name': 'bytes received',
        'unit': 'bytes',
    },
    BYTES_SENT: {
        'name': 'bytes sent',
        'unit': 'bytes',
    },
    PACKETS_RECEIVED: {
        'name': 'packets received',
        'unit': 'packets',
    },
    PACKETS_SENT: {
        'name': 'packets sent',
        'unit': 'packets',
    },
}

IN = 'received'
OUT = 'sent'
KBYTE = 1024


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the IGD sensors."""
    if discovery_info is None:
        return

    udn = discovery_info['udn']
    igd_device = hass.data[DOMAIN]['devices'][udn]

    # raw sensors + per-second sensors
    sensors = [
        RawIGDSensor(igd_device, name, sensor_type)
        for name, sensor_type in SENSOR_TYPES.items()
    ]
    sensors += [
        KBytePerSecondIGDSensor(igd_device, IN),
        KBytePerSecondIGDSensor(igd_device, OUT),
        PacketsPerSecondIGDSensor(igd_device, IN),
        PacketsPerSecondIGDSensor(igd_device, OUT),
    ]
    hass.data[DOMAIN]['sensors'][udn] = sensors
    async_add_devices(sensors, True)
    return True


class RawIGDSensor(Entity):
    """Representation of a UPnP IGD sensor."""

    def __init__(self, device, sensor_type_name, sensor_type):
        """Initialize the IGD sensor."""
        self._device = device
        self._type_name = sensor_type_name
        self._type = sensor_type
        self._name = '{} {}'.format(device.name, sensor_type['name'])
        self._state = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return '{}_{}'.format(self._device.udn, self._type_name)

    @property
    def state(self) -> str:
        """Return the state of the device."""
        return self._state

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return 'mdi:server-network'

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return self._type['unit']

    async def async_update(self):
        """Get the latest information from the IGD."""
        _LOGGER.debug('%s: async_update', self)
        if self._type_name == BYTES_RECEIVED:
            self._state = await self._device.async_get_total_bytes_received()
        elif self._type_name == BYTES_SENT:
            self._state = await self._device.async_get_total_bytes_sent()
        elif self._type_name == PACKETS_RECEIVED:
            self._state = await self._device.async_get_total_packets_received()
        elif self._type_name == PACKETS_SENT:
            self._state = await self._device.async_get_total_packets_sent()


class PerSecondIGDSensor(Entity):
    """Abstract representation of a X Sent/Received per second sensor."""

    def __init__(self, device, direction):
        """Initializer."""
        self._device = device
        self._direction = direction

        self._state = None
        self._last_value = None
        self._last_update_time = None

    @property
    def unit(self) -> str:
        """Unit we are measuring in."""
        raise NotImplementedError()

    @property
    def _async_fetch_value(self):
        """Fetch a value from the IGD."""
        raise NotImplementedError()

    @property
    def unique_id(self) -> str:
        """Return an unique ID."""
        return '{}_{}/sec_{}'.format(self._device.udn,
                                     self.unit,
                                     self._direction)

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return '{} {}/sec {}'.format(self._device.name,
                                     self.unit,
                                     self._direction)

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return 'mdi:server-network'

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement of this entity, if any."""
        return '{}/sec'.format(self.unit)

    def _is_overflowed(self, new_value) -> bool:
        """Check if value has overflowed."""
        return new_value < self._last_value

    async def async_update(self):
        """Get the latest information from the IGD."""
        _LOGGER.debug('%s: async_update', self)
        new_value = await self._async_fetch_value()

        if self._last_value is None:
            self._last_value = new_value
            self._last_update_time = datetime.now()
            return

        now = datetime.now()
        if self._is_overflowed(new_value):
            self._state = None  # temporarily report nothing
        else:
            delta_time = (now - self._last_update_time).seconds
            delta_value = new_value - self._last_value
            self._state = (delta_value / delta_time)

        self._last_value = new_value
        self._last_update_time = now


class KBytePerSecondIGDSensor(PerSecondIGDSensor):
    """Representation of a KBytes Sent/Received per second sensor."""

    @property
    def unit(self) -> str:
        """Unit we are measuring in."""
        return 'kbyte'

    async def _async_fetch_value(self) -> float:
        """"""
        if self._direction == IN:
            return await self._device.async_get_total_bytes_received()

        return await self._device.async_get_total_bytes_sent()

    @property
    def state(self):
        """Return the state of the device."""
        if self._state is None:
            return None

        return format(float(self._state / KBYTE), '.1f')


class PacketsPerSecondIGDSensor(PerSecondIGDSensor):
    """Representation of a Packets Sent/Received per second sensor."""

    @property
    def unit(self) -> str:
        """Unit we are measuring in."""
        return 'packets'

    async def _async_fetch_value(self) -> float:
        """"""
        if self._direction == IN:
            return await self._device.async_get_total_packets_received()

        return await self._device.async_get_total_packets_sent()

    @property
    def state(self):
        """Return the state of the device."""
        if self._state is None:
            return None

        return format(float(self._state), '.1f')
