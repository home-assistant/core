"""
Support for MAX! thermostats using the maxcul component

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/climate.maxcul/
"""
import logging

_LOGGER = logging.getLogger(__name__)

from homeassistant.components.climate import (
    ClimateDevice, SUPPORT_TARGET_TEMPERATURE, SUPPORT_OPERATION_MODE
)
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

from homeassistant.components.maxcul import (
    DATA_MAXCUL, DATA_DEVICES, EVENT_THERMOSTAT_UPDATE
)

DEPENDS = ['maxcul']

DEFAULT_TEMPERATURE = 12


def setup_platform(hass, config, add_devices, discovery_info=None):
    thermostat_id = discovery_info.get('device_id', None)
    if thermostat_id is None:
        return

    device = MaxCulClimate(hass, thermostat_id)
    add_devices([device])


class MaxCulClimate(ClimateDevice):
    """MAX! CUL climate device"""

    def __init__(
            self,
            hass,
            thermostat_id,
            current_temperature=None,
            target_temperature=None,
            mode=None,
            battery_low=None):
        self.entity_id = "climate.maxcul_thermostat_{:x}".format(thermostat_id)
        self._name = "Thermostat {:x}".format(thermostat_id)
        self._thermostat_id = thermostat_id
        self._maxcul_handle = hass.data[DATA_MAXCUL]
        self._current_temperature = current_temperature
        self._target_temperature = target_temperature
        self._mode = mode
        self._battery_low = battery_low

        def update(event):
            thermostat_id = event.data.get('device_id')
            if thermostat_id != self._thermostat_id:
                return

            current_temperature = event.data.get('measured_temperature')
            target_temperature = event.data.get('desired_temperature')
            mode = event.data.get('mode')
            battery_low = event.data.get('battery_low')

            if current_temperature is not None:
                self._current_temperature = current_temperature
            if target_temperature is not None:
                self._target_temperature = target_temperature
            if mode is not None:
                self._mode = mode
            if battery_low is not None:
                self._battery_low = battery_low

            self.async_schedule_update_ha_state()

        hass.bus.listen(EVENT_THERMOSTAT_UPDATE, update)

        self._maxcul_handle.wakeup(self._thermostat_id)

    @property
    def supported_features(self):
        return SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE

    @property
    def should_poll(self):
        return False

    @property
    def name(self):
        return self._name

    @property
    def max_temp(self):
        from maxcul import MAX_TEMPERATURE
        return MAX_TEMPERATURE

    @property
    def min_temp(self):
        from maxcul import MIN_TEMPERATURE
        return MIN_TEMPERATURE

    @property
    def temperature_unit(self):
        return TEMP_CELSIUS

    @property
    def current_temperature(self):
        return self._current_temperature

    @property
    def target_temperature(self):
        return self._target_temperature

    @property
    def current_operation(self):
        return self._mode

    @property
    def operation_list(self):
        from maxcul import MODE_AUTO, MODE_MANUAL, MODE_TEMPORARY, MODE_BOOST
        return [MODE_AUTO, MODE_MANUAL, MODE_TEMPORARY, MODE_BOOST]

    def set_temperature(self, **kwargs):
        from maxcul import MODE_MANUAL
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is None:
            return False

        try:
            self._maxcul_handle.set_temperature(
                self._thermostat_id,
                target_temperature,
                self._mode or MODE_MANUAL)
        except Exception as e:
            _LOGGER.error("Failed to set target temperature: {}".format(e))
            return False

    def set_operation_mode(self, operation_mode):
        try:
            self._maxcul_handle.set_temperature(
                self._thermostat_id,
                self._target_temperature or DEFAULT_TEMPERATURE,
                operation_mode)
        except Exception as e:
            _LOGGER.error("Failed to set operation mode: {}".format(e))
            return False
