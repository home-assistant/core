"""
Support for MAX! thermostats using the maxcul component.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.maxcul/
"""
import asyncio
import logging

import voluptuous as vol

from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE,
    PLATFORM_SCHEMA,
    STATE_AUTO, STATE_MANUAL, STATE_BOOST, STATE_TEMPORARY
)
from homeassistant.const import (
    TEMP_CELSIUS, ATTR_TEMPERATURE, CONF_ID,
    CONF_DEVICES
)
import homeassistant.helpers.config_validation as cv

from homeassistant.components.maxcul import (
    DATA_MAXCUL_CONNECTION, SIGNAL_THERMOSTAT_UPDATE
)

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['maxcul']

DEFAULT_TEMPERATURE = 12

SUPPORTED_OPERATIONS = [STATE_AUTO, STATE_MANUAL, STATE_BOOST, STATE_TEMPORARY]

DEVICE_SCHEMA = vol.Schema({
    vol.Required(CONF_ID): cv.positive_int
})

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_DEVICES): vol.Schema({
        cv.string: DEVICE_SCHEMA
    })
})


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Add a new MAX! thermostat."""
    maxcul_connection = hass.data[DATA_MAXCUL_CONNECTION]
    devices = [
        MaxThermostat(
            maxcul_connection,
            device[CONF_ID],
            name
        )
        for name, device
        in config[CONF_DEVICES].items()
    ]
    add_devices(devices)


class MaxThermostat(ClimateDevice):
    """A MAX! thermostat backed by a CUL stick."""

    def __init__(self, maxcul_connection, device_id, name):
        """Initialize a new device for the given thermostat id."""
        self._name = name
        self._device_id = device_id
        self._maxcul_connection = maxcul_connection
        self._current_temperature = None
        self._target_temperature = None
        self._mode = None
        self._battery_low = None

        self._maxcul_connection.add_paired_device(self._device_id)

    @asyncio.coroutine
    def async_added_to_hass(self):
        """Connect to thermostat update signal."""
        from maxcul import (
            ATTR_DEVICE_ID, ATTR_DESIRED_TEMPERATURE,
            ATTR_MEASURED_TEMPERATURE, ATTR_MODE,
            ATTR_BATTERY_LOW
        )

        @callback
        def update(payload):
            """Handle thermostat update events."""
            device_id = payload.get(ATTR_DEVICE_ID)
            if device_id != self._device_id:
                return

            current_temperature = payload.get(ATTR_MEASURED_TEMPERATURE)
            target_temperature = payload.get(ATTR_DESIRED_TEMPERATURE)
            mode = payload.get(ATTR_MODE)
            battery_low = payload.get(ATTR_BATTERY_LOW)

            if current_temperature is not None:
                self._current_temperature = current_temperature
            if target_temperature is not None:
                self._target_temperature = target_temperature
            if mode is not None:
                self._mode = mode
            if battery_low is not None:
                self._battery_low = battery_low

            self.async_schedule_update_ha_state()

        async_dispatcher_connect(
            self.hass, SIGNAL_THERMOSTAT_UPDATE, update)

        self._maxcul_connection.wakeup(self._device_id)

    @property
    def supported_features(self):
        """Return the features supported by this device."""
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def should_poll(self):
        """Return whether this device must be polled."""
        return False

    @property
    def name(self):
        """Return the name of this device."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific attributes."""
        from maxcul import ATTR_BATTERY_LOW
        return {
            ATTR_BATTERY_LOW: self._battery_low
        }

    @property
    def max_temp(self):
        """Return the maximum temperature for this device."""
        from maxcul import MAX_TEMPERATURE
        return MAX_TEMPERATURE

    @property
    def min_temp(self):
        """Return the minimum temperature for this device."""
        from maxcul import MIN_TEMPERATURE
        return MIN_TEMPERATURE

    @property
    def temperature_unit(self):
        """Return the temperature unit of this device."""
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        """Return the currently measured temperature of this device."""
        return self._current_temperature

    @property
    def target_temperature(self):
        """Return the target temperature of this device."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return the current operation mode of this device."""
        return self._mode_to_state(self._mode)

    @property
    def operation_list(self):
        """All supported operation modes of this device."""
        return SUPPORTED_OPERATIONS

    def set_temperature(self, **kwargs):
        """Set the target temperature of this device."""
        from maxcul import MODE_MANUAL
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return

        self._maxcul_connection.set_temperature(
            self._device_id,
            target_temperature,
            self._mode or MODE_MANUAL)

    def set_operation_mode(self, operation_mode):
        """Set the operation mode of this device."""
        new_mode = self._state_to_mode(operation_mode)
        if new_mode is None:
            return
        self._maxcul_connection.set_temperature(
            self._device_id,
            self._target_temperature or DEFAULT_TEMPERATURE,
            new_mode)

    @staticmethod
    def _state_to_mode(state):
        from maxcul import (
            MODE_AUTO, MODE_MANUAL, MODE_BOOST, MODE_TEMPORARY
        )
        return {
            STATE_AUTO: MODE_AUTO,
            STATE_MANUAL: MODE_MANUAL,
            STATE_BOOST: MODE_BOOST,
            STATE_TEMPORARY: MODE_TEMPORARY,
        }.get(state)

    @staticmethod
    def _mode_to_state(mode):
        from maxcul import (
            MODE_AUTO, MODE_MANUAL, MODE_BOOST, MODE_TEMPORARY
        )
        return {
            MODE_AUTO: STATE_AUTO,
            MODE_MANUAL: STATE_MANUAL,
            MODE_BOOST: STATE_BOOST,
            MODE_TEMPORARY: STATE_TEMPORARY,
        }.get(mode)
