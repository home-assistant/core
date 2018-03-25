"""Class to hold all light accessories."""
import logging

from homeassistant.components.light import (
    ATTR_HS_COLOR, ATTR_BRIGHTNESS, SUPPORT_BRIGHTNESS, SUPPORT_COLOR)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_ON, STATE_OFF

from . import TYPES
from .accessories import HomeAccessory, add_preload_service
from .const import (
    CATEGORY_LIGHT, SERV_LIGHTBULB,
    CHAR_BRIGHTNESS, CHAR_HUE, CHAR_ON, CHAR_SATURATION)

_LOGGER = logging.getLogger(__name__)

RGB_COLOR = 'rgb_color'


@TYPES.register('Light')
class Light(HomeAccessory):
    """Generate a Light accessory for a light entity.

    Currently supports: state, brightness, rgb_color.
    """

    def __init__(self, hass, entity_id, name, *args, **kwargs):
        """Initialize a new Light accessory object."""
        super().__init__(name, entity_id, CATEGORY_LIGHT, *args, **kwargs)

        self._hass = hass
        self._entity_id = entity_id
        self._flag = {CHAR_ON: False, CHAR_BRIGHTNESS: False,
                      CHAR_HUE: False, CHAR_SATURATION: False,
                      RGB_COLOR: False}

        self.chars = []
        self._features = self._hass.states.get(self._entity_id) \
            .attributes.get(ATTR_SUPPORTED_FEATURES)
        if self._features & SUPPORT_BRIGHTNESS:
            self.chars.append(CHAR_BRIGHTNESS)
        if self._features & SUPPORT_COLOR:
            self.chars.append(CHAR_HUE)
            self.chars.append(CHAR_SATURATION)
            self._hue = None
            self._saturation = None

        serv_light = add_preload_service(self, SERV_LIGHTBULB, self.chars)
        self.char_on = serv_light.get_characteristic(CHAR_ON)
        self.char_on.setter_callback = self.set_state
        self.char_on.value = 0

        if CHAR_BRIGHTNESS in self.chars:
            self.char_brightness = serv_light \
                .get_characteristic(CHAR_BRIGHTNESS)
            self.char_brightness.setter_callback = self.set_brightness
            self.char_brightness.value = 0
        if CHAR_HUE in self.chars:
            self.char_hue = serv_light.get_characteristic(CHAR_HUE)
            self.char_hue.setter_callback = self.set_hue
            self.char_hue.value = 0
        if CHAR_SATURATION in self.chars:
            self.char_saturation = serv_light \
                .get_characteristic(CHAR_SATURATION)
            self.char_saturation.setter_callback = self.set_saturation
            self.char_saturation.value = 75

    def set_state(self, value):
        """Set state if call came from HomeKit."""
        if self._flag[CHAR_BRIGHTNESS]:
            return

        _LOGGER.debug('%s: Set state to %d', self._entity_id, value)
        self._flag[CHAR_ON] = True
        self.char_on.set_value(value, should_callback=False)

        if value == 1:
            self._hass.components.light.turn_on(self._entity_id)
        elif value == 0:
            self._hass.components.light.turn_off(self._entity_id)

    def set_brightness(self, value):
        """Set brightness if call came from HomeKit."""
        _LOGGER.debug('%s: Set brightness to %d', self._entity_id, value)
        self._flag[CHAR_BRIGHTNESS] = True
        self.char_brightness.set_value(value, should_callback=False)
        self._hass.components.light.turn_on(
            self._entity_id, brightness_pct=value)

    def set_saturation(self, value):
        """Set saturation if call came from HomeKit."""
        _LOGGER.debug('%s: Set saturation to %d', self._entity_id, value)
        self._flag[CHAR_SATURATION] = True
        self.char_saturation.set_value(value, should_callback=False)
        self._saturation = value
        self.set_color()

    def set_hue(self, value):
        """Set hue if call came from HomeKit."""
        _LOGGER.debug('%s: Set hue to %d', self._entity_id, value)
        self._flag[CHAR_HUE] = True
        self.char_hue.set_value(value, should_callback=False)
        self._hue = value
        self.set_color()

    def set_color(self):
        """Set color if call came from HomeKit."""
        # Handle Color
        if self._features & SUPPORT_COLOR and self._flag[CHAR_HUE] and \
                self._flag[CHAR_SATURATION]:
            color = (self._hue, self._saturation)
            _LOGGER.debug('%s: Set hs_color to %s', self._entity_id, color)
            self._flag.update({
                CHAR_HUE: False, CHAR_SATURATION: False, RGB_COLOR: True})
            self._hass.components.light.turn_on(
                self._entity_id, hs_color=color)

    def update_state(self, entity_id=None, old_state=None, new_state=None):
        """Update light after state change."""
        if not new_state:
            return

        # Handle State
        state = new_state.state
        if not self._flag[CHAR_ON] and state in [STATE_ON, STATE_OFF] and \
                self.char_on.value != (state == STATE_ON):
            self.char_on.set_value(state == STATE_ON, should_callback=False)
        self._flag[CHAR_ON] = False

        # Handle Brightness
        if CHAR_BRIGHTNESS in self.chars:
            brightness = new_state.attributes.get(ATTR_BRIGHTNESS)
            if not self._flag[CHAR_BRIGHTNESS] and isinstance(brightness, int):
                brightness = round(brightness / 255 * 100, 0)
                if self.char_brightness.value != brightness:
                    self.char_brightness.set_value(brightness,
                                                   should_callback=False)
            self._flag[CHAR_BRIGHTNESS] = False

        # Handle Color
        if CHAR_SATURATION in self.chars and CHAR_HUE in self.chars:
            hue, saturation = new_state.attributes.get(
                ATTR_HS_COLOR, (None, None))
            if not self._flag[RGB_COLOR] and (
                    hue != self._hue or saturation != self._saturation):
                self.char_hue.set_value(hue, should_callback=False)
                self.char_saturation.set_value(saturation,
                                               should_callback=False)
            self._flag[RGB_COLOR] = False
