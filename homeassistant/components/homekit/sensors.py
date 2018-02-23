"""Class to hold all sensor accessories."""
import logging

from homeassistant.const import STATE_UNKNOWN
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    SERVICES_TEMPERATURE_SENSOR, CHAR_CURRENT_TEMPERATURE)


_LOGGER = logging.getLogger(__name__)


@TYPES.register('TemperatureSensor')
class TemperatureSensor(HomeAccessory):
    """Generate a TemperatureSensor accessory for a temperature sensor.

    Sensor entity must return either temperature in °C or STATE_UNKNOWN.
    """

    def __init__(self, hass, entity_id, display_name):
        """Initialize a TemperatureSensor accessory object."""
        super().__init__(display_name)
        self.set_category(self.ALL_CATEGORIES.SENSOR)
        self.set_accessory_info(entity_id)
        self.add_preload_service(SERVICES_TEMPERATURE_SENSOR)

        self._hass = hass
        self._entity_id = entity_id

        self.service_temp = self.get_service(SERVICES_TEMPERATURE_SENSOR)
        self.char_temp = self.service_temp. \
            get_characteristic(CHAR_CURRENT_TEMPERATURE)

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

        temperature = new_state.state
        if temperature != STATE_UNKNOWN:
            self.char_temp.set_value(float(temperature))
