"""Class to hold all thermostat accessories."""
import logging

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_OPERATION_MODE, STATE_HEAT, STATE_COOL,
    STATE_AUTO, SUPPORT_TARGET_TEMPERATURE_HIGH,
    SUPPORT_TARGET_TEMPERATURE_LOW)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT,
    ATTR_SUPPORTED_FEATURES, TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    SERV_THERMOSTAT, CHAR_CURRENT_HEATING_COOLING,
    CHAR_TARGET_HEATING_COOLING, CHAR_CURRENT_TEMPERATURE,
    CHAR_TARGET_TEMPERATURE, CHAR_TEMP_DISPLAY_UNITS,
    CHAR_COOLING_THRESHOLD_TEMPERATURE, CHAR_HEATING_THRESHOLD_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

UNIT_HASS_TO_HOMEKIT = {TEMP_CELSIUS: 0, TEMP_FAHRENHEIT: 1}
UNIT_HOMEKIT_TO_HASS = {c: s for s, c in UNIT_HASS_TO_HOMEKIT.items()}
THC_HASS_TO_HOMEKIT = {'off': 0, STATE_HEAT: 1, STATE_COOL: 2, STATE_AUTO: 3}
THC_HOMEKIT_TO_HASS = {c: s for s, c in THC_HASS_TO_HOMEKIT.items()}
CHC_HASS_TO_HOMEKIT = {'off': 0, STATE_HEAT: 1, STATE_COOL: 2}
CHC_HOMEKIT_TO_HASS = {c: s for s, c in CHC_HASS_TO_HOMEKIT.items()}


@TYPES.register('Thermostat')
class Thermostat(HomeAccessory):
    """Generate a Thermostat accessory for an alarm control panel."""

    def __init__(self, hass, entity_id, display_name):
        """Initialize a Thermostat accessory object."""
        super().__init__(display_name, entity_id, 'THERMOSTAT')

        self._hass = hass
        self._entity_id = entity_id
        self._call_timer = None

        self.heat_cool_flag_target_state = False
        self.temperature_flag_target_state = False
        self.cooling_thresh_temp_flag_target_state = False
        self.heating_thresh_temp_flag_target_state = False

        self.service_thermostat = add_preload_service(self, SERV_THERMOSTAT)
        self.char_current_heat_cool = self.service_thermostat. \
            get_characteristic(CHAR_CURRENT_HEATING_COOLING)
        self.char_current_heat_cool.value = 0
        self.char_target_heat_cool = self.service_thermostat. \
            get_characteristic(CHAR_TARGET_HEATING_COOLING)
        self.char_target_heat_cool.value = 0
        self.char_target_heat_cool.setter_callback = self.set_heat_cool

        self.char_current_temp = self.service_thermostat. \
            get_characteristic(CHAR_CURRENT_TEMPERATURE)
        self.char_current_temp.value = 0.0
        self.char_target_temp = self.service_thermostat. \
            get_characteristic(CHAR_TARGET_TEMPERATURE)
        self.char_target_temp.value = 0.0
        self.char_target_temp.setter_callback = self.set_target_temperature

        # If the device supports it: add high and low temperature
        supported_features = self._hass.states.get(self._entity_id). \
            attributes[ATTR_SUPPORTED_FEATURES]
        if supported_features is not None and \
                supported_features & SUPPORT_TARGET_TEMPERATURE_HIGH:
            self.char_cooling_thresh_temp = self.service_thermostat. \
                get_characteristic(CHAR_COOLING_THRESHOLD_TEMPERATURE)
            self.char_cooling_thresh_temp.value = 0.0
            self.char_cooling_thresh_temp.setter_callback = \
                self.set_cooling_threshold_temperature
        else:
            self.char_cooling_thresh_temp = None

        if supported_features is not None and \
                supported_features & SUPPORT_TARGET_TEMPERATURE_LOW:
            self.char_heating_thresh_temp = self.service_thermostat. \
                get_characteristic(CHAR_HEATING_THRESHOLD_TEMPERATURE)
            self.char_heating_thresh_temp.value = 0.0
            self.char_heating_thresh_temp.setter_callback = \
                self.set_heating_threshold_temperature
        else:
            self.char_heating_thresh_temp = None

        self.char_display_units = self.service_thermostat. \
            get_characteristic(CHAR_TEMP_DISPLAY_UNITS)
        self.char_display_units.value = 0

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_thermostat(new_state=state)

        async_track_state_change(self._hass, self._entity_id,
                                 self.update_thermostat)

    def set_heat_cool(self, value):
        """Move operation mode to value if call came from HomeKit."""
        if value in THC_HOMEKIT_TO_HASS:
            _LOGGER.debug("%s: Set heat-cool to %d", self._entity_id, value)
            self.heat_cool_flag_target_state = True
            hass_value = THC_HOMEKIT_TO_HASS[value]
            self._hass.services.call('climate', 'set_operation_mode',
                                     {ATTR_ENTITY_ID: self._entity_id,
                                      ATTR_OPERATION_MODE: hass_value})

    def set_cooling_threshold_temperature(self, value):
        """Set cooling threshold temperature temperature to value
        if call came from HomeKit."""
        _LOGGER.debug("%s: Set cooling threshold temperature to %.2f",
                      self._entity_id, value)
        self.cooling_thresh_temp_flag_target_state = True
        self._hass.services.call(
            'climate', 'set_temperature',
            {ATTR_ENTITY_ID: self._entity_id,
             ATTR_TARGET_TEMP_HIGH: value})

    def set_heating_threshold_temperature(self, value):
        """Set heating threshold temperature temperature to value
        if call came from HomeKit."""
        _LOGGER.debug("%s: Set heating threshold temperature to %.2f",
                      self._entity_id, value)
        self.heating_thresh_temp_flag_target_state = True
        self._hass.services.call(
            'climate', 'set_temperature',
            {ATTR_ENTITY_ID: self._entity_id,
             ATTR_TARGET_TEMP_LOW: value})

    def set_target_temperature(self, value):
        """Set target temperature to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set target temperature to %.2f",
                      self._entity_id, value)
        self.temperature_flag_target_state = True
        self._hass.services.call(
            'climate', 'set_temperature',
            {ATTR_ENTITY_ID: self._entity_id,
             ATTR_TEMPERATURE: value})

    def update_thermostat(self, entity_id=None,
                          old_state=None, new_state=None):
        """Update security state after state changed."""
        if new_state is None:
            return

        # Update current temperature
        current_temp = new_state.attributes[ATTR_CURRENT_TEMPERATURE]
        if current_temp is not None:
            self.char_current_temp.set_value(current_temp)

        # Update target temperature
        target_temp = new_state.attributes[ATTR_TEMPERATURE]
        if target_temp is not None and not self.temperature_flag_target_state:
            self.char_target_temp.set_value(target_temp,
                                            should_callback=False)

        # Update cooling threshold temperature
        if self.char_cooling_thresh_temp is not None:
            cooling_thresh_temp = new_state.attributes[ATTR_TARGET_TEMP_HIGH]
            if cooling_thresh_temp is not None and \
                    not self.cooling_thresh_temp_flag_target_state:
                self.char_cooling_thresh_temp.set_value(cooling_thresh_temp,
                                                        should_callback=False)

        # Update heating theshold temperature
        if self.char_heating_thresh_temp is not None:
            heating_thresh_temp = new_state.attributes[ATTR_TARGET_TEMP_LOW]
            if heating_thresh_temp is not None and \
                    not self.heating_thresh_temp_flag_target_state:
                self.char_heating_thresh_temp.set_value(heating_thresh_temp,
                                                        should_callback=False)

        # Update operation mode
        operation_mode = new_state.attributes[ATTR_OPERATION_MODE]
        target_operation_mode = operation_mode
        if operation_mode is not None and \
                operation_mode in THC_HASS_TO_HOMEKIT:
            # If operation mode is auto we have to change it
            # since it is not supported as current state in HomeKit
            if operation_mode == STATE_AUTO:
                if self.char_cooling_thresh_temp is None:
                    operation_mode = STATE_HEAT
                    target_operation_mode = STATE_HEAT
                else:
                    if self.char_current_temp.get_value() > \
                            self.char_cooling_thresh_temp.get_value():
                        operation_mode = STATE_COOL
                    elif self.char_current_temp.get_value() < \
                            self.char_heating_thresh_temp.get_value():
                        operation_mode = STATE_HEAT
                    else:
                        operation_mode = 'off'
            self.char_current_heat_cool.set_value(
                CHC_HASS_TO_HOMEKIT[operation_mode])

            if not self.heat_cool_flag_target_state:
                self.char_target_heat_cool.set_value(
                    THC_HASS_TO_HOMEKIT[target_operation_mode],
                    should_callback=False)

        # Update display units
        display_units = new_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        if display_units is not None and display_units in UNIT_HASS_TO_HOMEKIT:
            self.char_display_units.set_value(
                UNIT_HASS_TO_HOMEKIT[display_units])

        if self.char_current_heat_cool.get_value() \
                == self.char_target_heat_cool.get_value():
            self.heat_cool_flag_target_state = False

        self.temperature_flag_target_state = False
        self.cooling_thresh_temp_flag_target_state = False
        self.heating_thresh_temp_flag_target_state = False
