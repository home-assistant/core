"""
Support for MySensors lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mysensors/
"""
from homeassistant.components import mysensors
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_RGB_COLOR, ATTR_WHITE_VALUE, DOMAIN,
    SUPPORT_BRIGHTNESS, SUPPORT_RGB_COLOR, SUPPORT_WHITE_VALUE, Light)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util.color import rgb_hex_to_rgb_list

SUPPORT_MYSENSORS = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR |
                     SUPPORT_WHITE_VALUE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the MySensors platform for lights."""
    device_class_map = {
        'S_DIMMER': MySensorsLightDimmer,
        'S_RGB_LIGHT': MySensorsLightRGB,
        'S_RGBW_LIGHT': MySensorsLightRGBW,
    }
    mysensors.setup_mysensors_platform(
        hass, DOMAIN, discovery_info, device_class_map,
        add_devices=add_devices)


class MySensorsLight(mysensors.MySensorsEntity, Light):
    """Representation of a MySensors Light child node."""

    def __init__(self, *args):
        """Initialize a MySensors Light."""
        super().__init__(*args)
        self._state = None
        self._brightness = None
        self._rgb = None
        self._white = None

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """Return the RGB color value [int, int, int]."""
        return self._rgb

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return self._white

    @property
    def assumed_state(self):
        """Return true if unable to access real state of entity."""
        return self.gateway.optimistic

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    @property
    def supported_features(self):
        """Flag supported features."""
        return SUPPORT_MYSENSORS

    def _turn_on_light(self):
        """Turn on light child device."""
        set_req = self.gateway.const.SetReq

        if self._state:
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = True
            self._values[set_req.V_LIGHT] = STATE_ON

    def _turn_on_dimmer(self, **kwargs):
        """Turn on dimmer child device."""
        set_req = self.gateway.const.SetReq
        brightness = self._brightness

        if ATTR_BRIGHTNESS not in kwargs or \
                kwargs[ATTR_BRIGHTNESS] == self._brightness or \
                set_req.V_DIMMER not in self._values:
            return
        brightness = kwargs[ATTR_BRIGHTNESS]
        percent = round(100 * brightness / 255)
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_DIMMER, percent)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._brightness = brightness
            self._values[set_req.V_DIMMER] = percent

    def _turn_on_rgb_and_w(self, hex_template, **kwargs):
        """Turn on RGB or RGBW child device."""
        rgb = self._rgb
        white = self._white
        hex_color = self._values.get(self.value_type)
        new_rgb = kwargs.get(ATTR_RGB_COLOR)
        new_white = kwargs.get(ATTR_WHITE_VALUE)

        if new_rgb is None and new_white is None:
            return
        if new_rgb is not None:
            rgb = list(new_rgb)
        if hex_template == '%02x%02x%02x%02x':
            if new_white is not None:
                rgb.append(new_white)
            else:
                rgb.append(white)
        hex_color = hex_template % tuple(rgb)
        if len(rgb) > 3:
            white = rgb.pop()
        self.gateway.set_child_value(
            self.node_id, self.child_id, self.value_type, hex_color)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._rgb = rgb
            self._white = white
            self._values[self.value_type] = hex_color

    def turn_off(self, **kwargs):
        """Turn the device off."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self.gateway.set_child_value(
            self.node_id, self.child_id, value_type, 0)
        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = False
            self._values[value_type] = STATE_OFF
            self.schedule_update_ha_state()

    def _update_light(self):
        """Update the controller with values from light child."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        self._state = self._values[value_type] == STATE_ON

    def _update_dimmer(self):
        """Update the controller with values from dimmer child."""
        value_type = self.gateway.const.SetReq.V_DIMMER
        if value_type in self._values:
            self._brightness = round(255 * int(self._values[value_type]) / 100)
            if self._brightness == 0:
                self._state = False

    def _update_rgb_or_w(self):
        """Update the controller with values from RGB or RGBW child."""
        value = self._values[self.value_type]
        color_list = rgb_hex_to_rgb_list(value)
        if len(color_list) > 3:
            self._white = color_list.pop()
        self._rgb = color_list


class MySensorsLightDimmer(MySensorsLight):
    """Dimmer child class to MySensorsLight."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        if self.gateway.optimistic:
            self.schedule_update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        self._update_light()
        self._update_dimmer()


class MySensorsLightRGB(MySensorsLight):
    """RGB child class to MySensorsLight."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w('%02x%02x%02x', **kwargs)
        if self.gateway.optimistic:
            self.schedule_update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        self._update_light()
        self._update_dimmer()
        self._update_rgb_or_w()


class MySensorsLightRGBW(MySensorsLightRGB):
    """RGBW child class to MySensorsLightRGB."""

    # pylint: disable=too-many-ancestors

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w('%02x%02x%02x%02x', **kwargs)
        if self.gateway.optimistic:
            self.schedule_update_ha_state()
