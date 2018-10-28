"""
Demo platform that offers a fake water_heater device.

For more details about this platform, please refer to the documentation
https://home-assistant.io/components/demo/
"""
from homeassistant.components.water_heater import (
    WaterHeaterDevice,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_AWAY_MODE,
    SUPPORT_OPERATION_MODE)
from homeassistant.const import TEMP_FAHRENHEIT, ATTR_TEMPERATURE, TEMP_CELSIUS

SUPPORT_FLAGS_HEATER = (SUPPORT_TARGET_TEMPERATURE | SUPPORT_OPERATION_MODE |
                        SUPPORT_AWAY_MODE)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Demo water_heater devices."""
    add_entities([
        DemoWaterHeater('Demo Water Heater', 119,
                        TEMP_FAHRENHEIT, False, 'eco'),
        DemoWaterHeater('Demo Water Heater Celsius', 45,
                        TEMP_CELSIUS, True, 'eco')

    ])


class DemoWaterHeater(WaterHeaterDevice):
    """Representation of a demo water_heater device."""

    def __init__(self, name, target_temperature, unit_of_measurement,
                 away, current_operation):
        """Initialize the water_heater device."""
        self._name = name
        self._support_flags = SUPPORT_FLAGS_HEATER
        if target_temperature is not None:
            self._support_flags = \
                self._support_flags | SUPPORT_TARGET_TEMPERATURE
        if away is not None:
            self._support_flags = self._support_flags | SUPPORT_AWAY_MODE
        if current_operation is not None:
            self._support_flags = self._support_flags | SUPPORT_OPERATION_MODE
        self._target_temperature = target_temperature
        self._unit_of_measurement = unit_of_measurement
        self._away = away
        self._current_operation = current_operation
        self._operation_list = ['eco', 'electric', 'performance',
                                'high_demand', 'heat_pump', 'gas',
                                'off']

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return self._support_flags

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    @property
    def name(self):
        """Return the name of the water_heater device."""
        return self._name

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._target_temperature

    @property
    def current_operation(self):
        """Return current operation ie. heat, cool, idle."""
        return self._current_operation

    @property
    def operation_list(self):
        """Return the list of available operation modes."""
        return self._operation_list

    @property
    def is_away_mode_on(self):
        """Return if away mode is on."""
        return self._away

    def set_temperature(self, **kwargs):
        """Set new target temperatures."""
        self._target_temperature = kwargs.get(ATTR_TEMPERATURE)
        self.schedule_update_ha_state()

    def set_operation_mode(self, operation_mode):
        """Set new operation mode."""
        self._current_operation = operation_mode
        self.schedule_update_ha_state()

    def turn_away_mode_on(self):
        """Turn away mode on."""
        self._away = True
        self.schedule_update_ha_state()

    def turn_away_mode_off(self):
        """Turn away mode off."""
        self._away = False
        self.schedule_update_ha_state()
