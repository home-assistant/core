"""Support for the Sensors of an Intouch Lan2RF gateway."""
import logging

from homeassistant.const import (
    DEVICE_CLASS_PRESSURE,
    DEVICE_CLASS_SIGNAL_STRENGTH)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up an Intouch sensor entity."""
    client = hass.data[DOMAIN]['client']
    heater = hass.data[DOMAIN]['heater']

    async_add_entities([
        IntouchSignal(client, heater),
        IntouchPressure(client, heater)
    ])


class IntouchSensor(Entity):
    """Representation of an InTouch sensor."""

    def __init__(self, client, boiler):
        """Initialize the sensor."""
        self._client = client
        self._objref = boiler

        self._name = None
        self._device_class = None
        self._unit_of_measurement = None

    async def async_added_to_hass(self):
        """Set up a listener when this entity is added to HA."""
        async_dispatcher_connect(self.hass, DOMAIN, self._connect)

    @callback
    def _connect(self, packet):
        if packet['signal'] == 'refresh':
            self.async_schedule_update_ha_state(force_refresh=True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def device_class(self):
        """Return the device class of the sensor."""
        return self._device_class

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of the sensor."""
        return self._unit_of_measurement

    @property
    def should_poll(self) -> bool:
        """Return False as this device should never be polled."""
        return False


class IntouchPressure(IntouchSensor):
    """Representation of an InTouch CV Pressure sensor."""

    def __init__(self, client, boiler):
        """Initialize the sensor."""
        super().__init__(client, boiler)

        self._name = 'CV Pressure'
        self._device_class = DEVICE_CLASS_PRESSURE
        self._unit_of_measurement = 'bar'

    @property
    def state(self):
        """Return the state/value of the sensor."""
        return self._objref.status['pressure']

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        keys = ['is_pumping', 'heater_temp', 'tap_temp']
        return {k: self._objref.status[k] for k in keys}


class IntouchSignal(IntouchSensor):
    """Representation of an InTouch Signal strength sensor."""

    def __init__(self, client, boiler):
        """Initialize the signal strength sensor."""
        super().__init__(client, boiler)

        self._name = 'RF Signal'
        self._device_class = DEVICE_CLASS_SIGNAL_STRENGTH
        self._unit_of_measurement = 'dBm'

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._objref.status['rf_message_rssi']

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        return {k: self._objref.status[k] for k in ['nodenr', 'rfstatus_cntr']}
