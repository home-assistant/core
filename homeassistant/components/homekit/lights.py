"""Class to hold all light accesories."""
import logging

from homeassistant.const import STATE_UNKNOWN
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
        _LOGGER.debug("Loading light component1")
        """Initialize a LightBulb accessory object."""
        super().__init__(display_name)
        self.set_category(self.ALL_CATEGORIES.LIGHTBULB)
        _LOGGER.debug("Loading light component2")
        self.set_accessory_info(entity_id)
        _LOGGER.debug("Loading light component3")
        self.add_preload_service(SERVICES_LIGHTBULB)
        _LOGGER.debug("Loading light component4")

        self._hass = hass
        self._entity_id = entity_id

        self.brightness = None

        _LOGGER.debug("Loading light component5")

        self.service_lightbulb = self.get_service(SERVICES_LIGHTBULB)
        _LOGGER.debug("Loading light component6")
        #self.char_brightness = self.service_lightbulb. \
        #    get_characteristic(CHAR_BRIGHTNESS)
        _LOGGER.debug("Loading light component7")
        self.char_state = self.service_lightbulb. \
            get_characteristic(CHAR_STATE)
        _LOGGER.debug("Loading light component8")

        #self.char_brightness.setter_callback = self.set_brightness
        _LOGGER.debug("Loading light component9")
        self.char_state.setter_callback = self.set_state
        _LOGGER.debug("Loading light component10")

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
        _LOGGER.debug(str(value))

    def update_state(self, entity_id=None, old_state=None,
                              new_state=None):
        return True