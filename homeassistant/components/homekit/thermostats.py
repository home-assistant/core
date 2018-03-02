"""Class to hold all thermostat accessories."""
import logging
from threading import Timer

from homeassistant.components.climate import (ATTR_CURRENT_TEMPERATURE,
                                              ATTR_TEMPERATURE,
                                              ATTR_OPERATION_MODE,
                                              STATE_HEAT, STATE_COOL)
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (SERV_THERMOSTAT, CHAR_CURRENT_HEATING_COOLING,
                    CHAR_TARGET_HEATING_COOLING, CHAR_CURRENT_TEMPERATURE,
                    CHAR_TARGET_TEMPERATURE, CHAR_TEMP_DISPLAY_UNITS)

_LOGGER = logging.getLogger(__name__)

UNIT_HASS_TO_HOMEKIT = {'°C': 0, '°F': 1}
UNIT_HOMEKIT_TO_HASS = {c: s for s, c in UNIT_HASS_TO_HOMEKIT.items()}
HC_HASS_TO_HOMEKIT = {'off': 0, STATE_HEAT: 1, STATE_COOL: 2}
HC_HOMEKIT_TO_HASS = {c: s for s, c in HC_HASS_TO_HOMEKIT.items()}


@TYPES.register('Thermostat')
class Thermostat(HomeAccessory):
    """Generate a Thermostat accessory for an alarm control panel."""

    def __init__(self, hass, entity_id, display_name):
        """Initialize a Thermostat accessory object."""
        super().__init__(display_name, entity_id, 'THERMOSTAT')

        self._hass = hass
        self._entity_id = entity_id
        self._call_timer = None

        self.current_heat_cool = None
        self.homekit_target_heat_cool = None
        self.current_temperature = None
        self.homekit_target_temperature = None
        self.target_temperature = None
        self.display_units = None

        self.service_thermostat = add_preload_service(self, SERV_THERMOSTAT)
        self.char_current_heat_cool = self.service_thermostat.\
            get_characteristic(CHAR_CURRENT_HEATING_COOLING)
        self.char_target_heat_cool = self.service_thermostat.\
            get_characteristic(CHAR_TARGET_HEATING_COOLING)
        self.char_target_heat_cool.setter_callback = self.set_heat_cool

        self.char_current_temp = self.service_thermostat.\
            get_characteristic(CHAR_CURRENT_TEMPERATURE)
        self.char_target_temp = self.service_thermostat.\
            get_characteristic(CHAR_TARGET_TEMPERATURE)
        self.char_target_temp.setter_callback = self.set_temperature_debounced

        self.char_display_units = self.service_thermostat.\
            get_characteristic(CHAR_TEMP_DISPLAY_UNITS)

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_thermostat(new_state=state)

        async_track_state_change(self._hass, self._entity_id,
                                 self.update_thermostat)

    def set_heat_cool(self, value):
        """Move operation mode to value if call came from HomeKit."""
        if value != self.current_heat_cool and value in HC_HOMEKIT_TO_HASS:
            _LOGGER.debug("%s: Set heat-cool to %d", self._entity_id, value)
            self.homekit_target_heat_cool = value
            hass_value = HC_HOMEKIT_TO_HASS[value]

            self._hass.services.call('climate', 'set_operation_mode',
                                     {'entity_id': self._entity_id,
                                      'operation_mode': hass_value})

    def set_temperature_debounced(self, value):
        _LOGGER.debug("%s: Call to set temperature to %.2f",
                      self._entity_id, value)

        def perform_call():
            self.set_target_temperature(value)
        # Cancel timer if one was running
        if self._call_timer is not None:
            try:
                self._call_timer.cancel()
            except AttributeError:
                pass
        self._call_timer = Timer(1, perform_call)
        self._call_timer.start()

    def set_target_temperature(self, value):
        """Set target temperature to value if call came from HomeKit."""
        if value != self.target_temperature:
            _LOGGER.debug("%s: Set target temperature to %.2f",
                          self._entity_id, value)
            self.homekit_target_temperature = value
            self._hass.services.call('climate', 'set_temperature',
                                     {'entity_id': self._entity_id,
                                      'temperature':
                                          self.homekit_target_temperature})

    def update_thermostat(self, entity_id=None,
                          old_state=None, new_state=None):
        """Update security state after state changed."""
        if new_state is None:
            return

        current_temp = new_state.attributes[ATTR_CURRENT_TEMPERATURE]
        if current_temp is not None:
            self.current_temperature = float(current_temp)
            self.char_current_temp.set_value(self.current_temperature)
        target_temp = new_state.attributes[ATTR_TEMPERATURE]
        if target_temp is not None:
            self.target_temperature = float(target_temp)
            self.char_target_temp.set_value(self.target_temperature)
        operation_mode = new_state.attributes[ATTR_OPERATION_MODE]
        if operation_mode is not None and operation_mode in HC_HASS_TO_HOMEKIT:
            self.current_heat_cool = HC_HASS_TO_HOMEKIT[operation_mode]
            self.char_current_heat_cool.set_value(self.current_heat_cool)
        display_units = new_state.attributes['unit_of_measurement']
        if display_units is not None and display_units in UNIT_HASS_TO_HOMEKIT:
            self.display_units = UNIT_HASS_TO_HOMEKIT[display_units]
            self.char_display_units.set_value(self.display_units)

        if (self.homekit_target_heat_cool is None
            and self.current_heat_cool is not None) \
                or self.homekit_target_heat_cool == self.current_heat_cool:
            self.char_target_heat_cool.set_value(self.current_heat_cool,
                                                 should_callback=False)
            self.homekit_target_heat_cool = None

        if self.homekit_target_temperature is None \
                or self.homekit_target_temperature == self.target_temperature:
            self.homekit_target_temperature = None
