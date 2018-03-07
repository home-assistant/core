"""Class to hold all thermostat accessories."""
import logging

from homeassistant.components.climate import (
    ATTR_CURRENT_TEMPERATURE, ATTR_TEMPERATURE,
    ATTR_TARGET_TEMP_HIGH, ATTR_TARGET_TEMP_LOW,
    ATTR_OPERATION_MODE, ATTR_OPERATION_LIST,
    STATE_HEAT, STATE_COOL, STATE_AUTO)
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_UNIT_OF_MEASUREMENT,
    TEMP_CELSIUS, TEMP_FAHRENHEIT)
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    SERV_THERMOSTAT, CHAR_CURRENT_HEATING_COOLING,
    CHAR_TARGET_HEATING_COOLING, CHAR_CURRENT_TEMPERATURE,
    CHAR_TARGET_TEMPERATURE, CHAR_TEMP_DISPLAY_UNITS,
    CHAR_COOLING_THRESHOLD_TEMPERATURE, CHAR_HEATING_THRESHOLD_TEMPERATURE)

_LOGGER = logging.getLogger(__name__)

STATE_OFF = 'off'
UNIT_HASS_TO_HOMEKIT = {TEMP_CELSIUS: 0, TEMP_FAHRENHEIT: 1}
UNIT_HOMEKIT_TO_HASS = {c: s for s, c in UNIT_HASS_TO_HOMEKIT.items()}
HC_HASS_TO_HOMEKIT = {STATE_OFF: 0, STATE_HEAT: 1,
                      STATE_COOL: 2, STATE_AUTO: 3}
HC_HOMEKIT_TO_HASS = {c: s for s, c in HC_HASS_TO_HOMEKIT.items()}


@TYPES.register('Thermostat')
class Thermostat(HomeAccessory):
    """Generate a Thermostat accessory for a climate."""

    def __init__(self, hass, entity_id, display_name, support_auto=False):
        """Initialize a Thermostat accessory object."""
        super().__init__(display_name, entity_id, 'THERMOSTAT')

        self._hass = hass
        self._entity_id = entity_id
        self._call_timer = None

        self.heat_cool_flag_target_state = False
        self.temperature_flag_target_state = False
        self.coolingthresh_flag_target_state = False
        self.heatingthresh_flag_target_state = False

        extra_chars = None
        # Add additional characteristics if auto mode is supported
        if support_auto:
            extra_chars = [CHAR_COOLING_THRESHOLD_TEMPERATURE,
                           CHAR_HEATING_THRESHOLD_TEMPERATURE]

        # Preload the thermostat service
        self.service_thermostat = add_preload_service(self, SERV_THERMOSTAT,
                                                      extra_chars)

        # Current and target mode characteristics
        self.char_current_heat_cool = self.service_thermostat. \
            get_characteristic(CHAR_CURRENT_HEATING_COOLING)
        self.char_current_heat_cool.value = 0
        self.char_target_heat_cool = self.service_thermostat. \
            get_characteristic(CHAR_TARGET_HEATING_COOLING)
        self.char_target_heat_cool.value = 0
        self.char_target_heat_cool.setter_callback = self.set_heat_cool

        # Current and target temperature characteristics
        self.char_current_temp = self.service_thermostat. \
            get_characteristic(CHAR_CURRENT_TEMPERATURE)
        self.char_current_temp.value = 21.0
        self.char_target_temp = self.service_thermostat. \
            get_characteristic(CHAR_TARGET_TEMPERATURE)
        self.char_target_temp.value = 21.0
        self.char_target_temp.setter_callback = self.set_target_temperature

        # Display units characteristic
        self.char_display_units = self.service_thermostat. \
            get_characteristic(CHAR_TEMP_DISPLAY_UNITS)
        self.char_display_units.value = 0

        # If the device supports it: high and low temperature characteristics
        if support_auto:
            self.char_cooling_thresh_temp = self.service_thermostat. \
                get_characteristic(CHAR_COOLING_THRESHOLD_TEMPERATURE)
            self.char_cooling_thresh_temp.value = 23.0
            self.char_cooling_thresh_temp.setter_callback = \
                self.set_cooling_threshold

            self.char_heating_thresh_temp = self.service_thermostat. \
                get_characteristic(CHAR_HEATING_THRESHOLD_TEMPERATURE)
            self.char_heating_thresh_temp.value = 19.0
            self.char_heating_thresh_temp.setter_callback = \
                self.set_heating_threshold
        else:
            self.char_cooling_thresh_temp = None
            self.char_heating_thresh_temp = None

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_thermostat(new_state=state)

        async_track_state_change(self._hass, self._entity_id,
                                 self.update_thermostat)

    def set_heat_cool(self, value):
        """Move operation mode to value if call came from HomeKit."""
        if value in HC_HOMEKIT_TO_HASS:
            _LOGGER.debug("%s: Set heat-cool to %d", self._entity_id, value)
            self.heat_cool_flag_target_state = True
            hass_value = HC_HOMEKIT_TO_HASS[value]
            self._hass.services.call('climate', 'set_operation_mode',
                                     {ATTR_ENTITY_ID: self._entity_id,
                                      ATTR_OPERATION_MODE: hass_value})

    def set_cooling_threshold(self, value):
        """Set cooling threshold temp to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set cooling threshold temperature to %.2f",
                      self._entity_id, value)
        self.coolingthresh_flag_target_state = True
        low = self.char_heating_thresh_temp.get_value()
        self._hass.services.call(
            'climate', 'set_temperature',
            {ATTR_ENTITY_ID: self._entity_id,
             ATTR_TARGET_TEMP_HIGH: value,
             ATTR_TARGET_TEMP_LOW: low})

    def set_heating_threshold(self, value):
        """Set heating threshold temp to value if call came from HomeKit."""
        _LOGGER.debug("%s: Set heating threshold temperature to %.2f",
                      self._entity_id, value)
        self.heatingthresh_flag_target_state = True
        # Home assistant always wants to set low and high at the same time
        high = self.char_cooling_thresh_temp.get_value()
        self._hass.services.call(
            'climate', 'set_temperature',
            {ATTR_ENTITY_ID: self._entity_id,
             ATTR_TARGET_TEMP_LOW: value,
             ATTR_TARGET_TEMP_HIGH: high})

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
        current_temp = new_state.attributes.get(ATTR_CURRENT_TEMPERATURE)
        if current_temp is not None:
            self.char_current_temp.set_value(current_temp)

        # Update target temperature
        target_temp = new_state.attributes.get(ATTR_TEMPERATURE)
        if target_temp is not None:
            if not self.temperature_flag_target_state:
                self.char_target_temp.set_value(target_temp,
                                                should_callback=False)
            else:
                self.temperature_flag_target_state = False

        # Update cooling threshold temperature if characteristic exists
        if self.char_cooling_thresh_temp is not None:
            cooling_thresh = new_state.attributes.get(ATTR_TARGET_TEMP_HIGH)
            if cooling_thresh is not None:
                if not self.coolingthresh_flag_target_state:
                    self.char_cooling_thresh_temp.set_value(
                        cooling_thresh, should_callback=False)
                else:
                    self.coolingthresh_flag_target_state = False

        # Update heating threshold temperature if characteristic exists
        if self.char_heating_thresh_temp is not None:
            heating_thresh = new_state.attributes.get(ATTR_TARGET_TEMP_LOW)
            if heating_thresh is not None:
                if not self.heatingthresh_flag_target_state:
                    self.char_heating_thresh_temp.set_value(
                        heating_thresh, should_callback=False)
                else:
                    self.heatingthresh_flag_target_state = False

        # Update display units
        display_units = new_state.attributes.get(ATTR_UNIT_OF_MEASUREMENT)
        if display_units is not None \
                and display_units in UNIT_HASS_TO_HOMEKIT:
            self.char_display_units.set_value(
                UNIT_HASS_TO_HOMEKIT[display_units])

        # Update target operation mode
        operation_mode = new_state.attributes.get(ATTR_OPERATION_MODE)
        if operation_mode is not None \
                and operation_mode in HC_HASS_TO_HOMEKIT:
            if not self.heat_cool_flag_target_state:
                self.char_target_heat_cool.set_value(
                    HC_HASS_TO_HOMEKIT[operation_mode], should_callback=False)
            else:
                self.heat_cool_flag_target_state = False

        # Set current operation mode based on temperatures and target mode
        if operation_mode == STATE_HEAT:
            if current_temp < target_temp:
                current_operation_mode = STATE_HEAT
            else:
                current_operation_mode = STATE_OFF
        elif operation_mode == STATE_COOL:
            if current_temp > target_temp:
                current_operation_mode = STATE_COOL
            else:
                current_operation_mode = STATE_OFF
        elif operation_mode == STATE_AUTO:
            # Check if auto is supported
            if self.char_cooling_thresh_temp is not None:
                lower_temp = self.char_heating_thresh_temp.get_value()
                upper_temp = self.char_cooling_thresh_temp.get_value()
                if current_temp < lower_temp:
                    current_operation_mode = STATE_HEAT
                elif current_temp > upper_temp:
                    current_operation_mode = STATE_COOL
                else:
                    current_operation_mode = STATE_OFF
            else:
                # Check if heating or cooling are supported
                heat = STATE_HEAT in new_state.attributes[ATTR_OPERATION_LIST]
                cool = STATE_COOL in new_state.attributes[ATTR_OPERATION_LIST]
                if current_temp < target_temp and heat:
                    current_operation_mode = STATE_HEAT
                elif current_temp > target_temp and cool:
                    current_operation_mode = STATE_COOL
                else:
                    current_operation_mode = STATE_OFF
        else:
            current_operation_mode = STATE_OFF

        self.char_current_heat_cool.set_value(
            HC_HASS_TO_HOMEKIT[current_operation_mode])
