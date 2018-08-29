"""
Support for UPnP Sensors (IGD).

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.upnp/
"""
import logging

from homeassistant.components import history
from homeassistant.components.igd import DOMAIN, UNITS
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['igd', 'history']

BYTES_RECEIVED = 'bytes_received'
BYTES_SENT = 'bytes_sent'
PACKETS_RECEIVED = 'packets_received'
PACKETS_SENT = 'packets_sent'

# sensor_type: [friendly_name, convert_unit, icon]
SENSOR_TYPES = {
    BYTES_RECEIVED: ['bytes received', True, 'mdi:server-network', float],
    BYTES_SENT: ['bytes sent', True, 'mdi:server-network', float],
    PACKETS_RECEIVED: ['packets received', False, 'mdi:server-network', int],
    PACKETS_SENT: ['packets sent', False, 'mdi:server-network', int],
}

OVERFLOW_AT = 2**32


async def async_setup_platform(hass, config, async_add_devices,
                               discovery_info=None):
    """Set up the IGD sensors."""
    if discovery_info is None:
        return

    udn = discovery_info['udn']
    device = hass.data[DOMAIN]['devices'][udn]
    unit = discovery_info['unit']
    async_add_devices([
        IGDSensor(device, t, unit if SENSOR_TYPES[t][1] else '#')
        for t in SENSOR_TYPES])


class IGDSensor(Entity):
    """Representation of a UPnP IGD sensor."""

    def __init__(self, device, sensor_type, unit=None):
        """Initialize the IGD sensor."""
        self._device = device
        self.type = sensor_type
        self.unit = unit
        self.unit_factor = UNITS[unit] if unit in UNITS else 1
        self._name = 'IGD {}'.format(SENSOR_TYPES[sensor_type][0])
        self._state = None
        self._last_value = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the device."""
        if self._state is None:
            return None

        coercer = SENSOR_TYPES[self.type][3]
        if coercer == int:
            return format(self._state)

        return format(self._state / self.unit_factor, '.1f')

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return SENSOR_TYPES[self.type][2]

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return self.unit

    async def async_update(self):
        """Get the latest information from the IGD."""
        new_value = 0
        if self.type == BYTES_RECEIVED:
            new_value = await self._device.async_get_total_bytes_received()
        elif self.type == BYTES_SENT:
            new_value = await self._device.async_get_total_bytes_sent()
        elif self.type == PACKETS_RECEIVED:
            new_value = await self._device.async_get_total_packets_received()
        elif self.type == PACKETS_SENT:
            new_value = await self._device.async_get_total_packets_sent()

        self._handle_new_value(new_value)

        # _LOGGER.debug('Removing self: %s', self)
        # await self.async_remove()  # XXX TODO: does not remove from the UI

    @property
    def _last_state(self):
        """Get the last state reported to hass."""
        states = history.get_last_state_changes(self.hass, 2, self.entity_id)
        entity_states = [
            state for state in states[self.entity_id]
            if state.state != 'unknown']
        _LOGGER.debug('%s: entity_states: %s', self.entity_id, entity_states)
        if not entity_states:
            return None

        return entity_states[0]

    @property
    def _last_value_from_state(self):
        """Get the last value reported to hass."""
        last_state = self._last_state
        if not last_state:
            _LOGGER.debug('%s: No last state', self.entity_id)
            return None

        coercer = SENSOR_TYPES[self.type][3]
        try:
            state = coercer(float(last_state.state)) * self.unit_factor
        except ValueError:
            _LOGGER.debug('%s: value error, coercer: %s, state: %s', self.entity_id, coercer, last_state.state)
            raise
            state = coercer(0.0)

        return state

    def _handle_new_value(self, new_value):
        _LOGGER.debug('%s: handle_new_value: state: %s, new_value: %s, last_value: %s',
                      self.entity_id, self._state, new_value, self._last_value)

        # ❯❯❯ upnp-client --debug --pprint --device http://192.168.178.1/RootDevice.xml call-action WANCIFC/GetTotalBytesReceived
        if self.entity_id is None:
            # don't know our entity ID yet, do nothing but store value
            self._last_value = new_value
            return

        if self._last_value is None:
            self._last_value = new_value

        if self._state is None:
            # try to get the state from history
            self._state = self._last_value_from_state or 0

        _LOGGER.debug('%s: state: %s, last_value: %s',
                      self.entity_id, self._state, self._last_value)

        # calculate new state
        if self._last_value <= new_value:
            diff = new_value - self._last_value
        else:
            # handle overflow
            diff = OVERFLOW_AT - self._last_value
            if new_value >= 0:
                diff += new_value
            else:
                # some devices don't overflow and start at 0, but somewhere to -2**32
                diff += new_value - -OVERFLOW_AT

        self._state += diff
        self._last_value = new_value
        _LOGGER.debug('%s: diff: %s, state: %s, last_value: %s',
                      self.entity_id, diff, self._state, self._last_value)
