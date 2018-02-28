"""Class to hold all sensor accessories."""
import logging

from homeassistant.const import (
    ATTR_UNIT_OF_MEASUREMENT, TEMP_FAHRENHEIT, TEMP_CELSIUS)
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import (
    HomeAccessory, add_preload_service, override_properties)
from .const import (
    SERV_TEMPERATURE_SENSOR, CHAR_CURRENT_TEMPERATURE, PROP_CELSIUS)


_LOGGER = logging.getLogger(__name__)


def calc_temperature(state, unit=TEMP_CELSIUS):
    """Calculate temperature from state and unit.

    Always return temperature as Celsius value.
    Conversion is handled on the device.
    """
    try:
        value = float(state)
    except ValueError:
        return None

    return round((value - 32) / 1.8, 2) if unit == TEMP_FAHRENHEIT else value


@TYPES.register('TemperatureSensor')
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return temperature in °C, °F.
    """

    def __init__(self, hass, entity_id, display_name):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(display_name, entity_id, 'SENSOR')

        self._hass = hass
        self._entity_id = entity_id

        self.serv_temp = add_preload_service(self, SERV_TEMPERATURE_SENSOR)
        self.char_temp = self.serv_temp. \
            get_characteristic(CHAR_CURRENT_TEMPERATURE)
        override_properties(self.char_temp, PROP_CELSIUS)
        self.char_temp.value = 0
        self.unit = None

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_temperature(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_temperature)

    def update_temperature(self, entity_id=None, old_state=None,
                           new_state=None):
        """Update temperature after state changed."""
        if new_state is None:
            return

        unit = new_state.attributes[ATTR_UNIT_OF_MEASUREMENT]
        temperature = calc_temperature(new_state.state, unit)
        if temperature is not None:
            self.char_temp.set_value(temperature)
            _LOGGER.debug("%s: Current temperature set to %d°C",
                          self._entity_id, temperature)
