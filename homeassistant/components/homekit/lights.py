"""Class to hold all light accesories."""
import logging

from homeassistant.components.light import ATTR_BRIGHTNESS
from homeassistant.helpers.event import async_track_state_change

from . import TYPES
from .accessories import HomeAccessory
from .const import (
    SERVICES_LIGHTBULB, CHAR_BRIGHTNESS, CHAR_STATE)


_LOGGER = logging.getLogger(__name__)


@TYPES.register('Lightbulb')
class Lightbulb(HomeAccessory):
    """Generate a Light accessory for a lightbulb."""

    def __init__(self, hass, entity_id, display_name):
        _LOGGER.debug("Loading light component")
        """Initialize a LightBulb accessory object."""
        super().__init__(display_name)
        self.set_category(self.ALL_CATEGORIES.LIGHTBULB)
        self.set_accessory_info(entity_id)
        self.add_preload_service(SERVICES_LIGHTBULB)

        self._hass = hass
        self._entity_id = entity_id

        self.brightness = None

        self.service_lightbulb = self.get_service(SERVICES_LIGHTBULB)
        #self.char_brightness = self.service_lightbulb. \
        #    get_characteristic(CHAR_BRIGHTNESS)
        self.char_state = self.service_lightbulb. \
            get_characteristic(CHAR_STATE)

        #self.char_brightness.setter_callback = self.set_brightness
        self.char_state.setter_callback = self.set_state

    def run(self):
        """Method called be object after driver is started."""
        state = self._hass.states.get(self._entity_id)
        self.update_state(new_state=state)

        async_track_state_change(
            self._hass, self._entity_id, self.update_state)

    def set_brightness(self, value):
        pass

    def update_brightness(self, entity_id=None, old_state=None,
                              new_state=None):
        pass

    def set_state(self, value):
        """Receives command from Homekit."""
        new_state = value == 1
        action = 'turn_on' if new_state else 'turn_off'

        # Send to Home Assistant
        self._hass.services.call(
            'light', action,
            {'entity_id': self._entity_id}
        )

    def update_state(self, entity_id=None, old_state=None,
                              new_state=None):
        """Updates the Homekit value of the accessory."""
        state = new_state.state == 'on'

        self.char_state.set_value(state)
