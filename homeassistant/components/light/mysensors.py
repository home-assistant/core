"""
Support for MySensors lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mysensors/
"""
# pylint: disable=abstract-method
import logging

from homeassistant.components import mysensors
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_RGB_COLOR,
                                            ATTR_WHITE_VALUE,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_RGB_COLOR,
                                            SUPPORT_WHITE_VALUE, Light)
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.util.color import rgb_hex_to_rgb_list

_LOGGER = logging.getLogger(__name__)
ATTR_VALUE = 'value'
ATTR_VALUE_TYPE = 'value_type'

SUPPORT_MYSENSORS = (SUPPORT_BRIGHTNESS | SUPPORT_RGB_COLOR |
                     SUPPORT_WHITE_VALUE)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Setup the mysensors platform for sensors."""
    # Only act if loaded via mysensors by discovery event.
    # Otherwise gateway is not setup.
    if discovery_info is None:
        return

    for gateway in mysensors.GATEWAYS.values():
        # Define the S_TYPES and V_TYPES that the platform should handle as
        # states. Map them in a dict of lists.
        pres = gateway.const.Presentation
        set_req = gateway.const.SetReq
        map_sv_types = {
            pres.S_DIMMER: [set_req.V_DIMMER],
        }
        device_class_map = {
            pres.S_DIMMER: MySensorsLightDimmer,
        }
        if float(gateway.protocol_version) >= 1.5:
            map_sv_types.update({
                pres.S_RGB_LIGHT: [set_req.V_RGB],
                pres.S_RGBW_LIGHT: [set_req.V_RGBW],
            })
            map_sv_types[pres.S_DIMMER].append(set_req.V_PERCENTAGE)
            device_class_map.update({
                pres.S_RGB_LIGHT: MySensorsLightRGB,
                pres.S_RGBW_LIGHT: MySensorsLightRGBW,
            })
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, device_class_map))


class MySensorsLight(mysensors.MySensorsDeviceEntity, Light):
    """Represent the value of a MySensors Light child node."""

    def __init__(self, *args):
        """Setup instance attributes."""
        mysensors.MySensorsDeviceEntity.__init__(self, *args)
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

        if self._state or set_req.V_LIGHT not in self._values:
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, set_req.V_LIGHT, 1)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = True
            self._values[set_req.V_LIGHT] = STATE_ON
            self.update_ha_state()

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
            self.update_ha_state()

    def _turn_on_rgb_and_w(self, hex_template, **kwargs):
        """Turn on RGB or RGBW child device."""
        rgb = self._rgb
        white = self._white
        hex_color = self._values.get(self.value_type)

        if ATTR_WHITE_VALUE in kwargs and \
                kwargs[ATTR_WHITE_VALUE] != self._white:
            white = kwargs[ATTR_WHITE_VALUE]

        if ATTR_RGB_COLOR in kwargs and \
                kwargs[ATTR_RGB_COLOR] != self._rgb:
            rgb = list(kwargs[ATTR_RGB_COLOR])
            if white is not None and hex_template == '%02x%02x%02x%02x':
                rgb.append(white)
            hex_color = hex_template % tuple(rgb)
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, hex_color)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._rgb = rgb
            self._white = white
            if hex_color:
                self._values[self.value_type] = hex_color
            self.update_ha_state()

    def _turn_off_light(self, value_type=None, value=None):
        """Turn off light child device."""
        set_req = self.gateway.const.SetReq
        value_type = (
            set_req.V_LIGHT
            if set_req.V_LIGHT in self._values else value_type)
        value = 0 if set_req.V_LIGHT in self._values else value
        return {ATTR_VALUE_TYPE: value_type, ATTR_VALUE: value}

    def _turn_off_dimmer(self, value_type=None, value=None):
        """Turn off dimmer child device."""
        set_req = self.gateway.const.SetReq
        value_type = (
            set_req.V_DIMMER
            if set_req.V_DIMMER in self._values else value_type)
        value = 0 if set_req.V_DIMMER in self._values else value
        return {ATTR_VALUE_TYPE: value_type, ATTR_VALUE: value}

    def _turn_off_rgb_or_w(self, value_type=None, value=None):
        """Turn off RGB or RGBW child device."""
        if float(self.gateway.protocol_version) >= 1.5:
            set_req = self.gateway.const.SetReq
            if self.value_type == set_req.V_RGB:
                value = '000000'
            elif self.value_type == set_req.V_RGBW:
                value = '00000000'
        return {ATTR_VALUE_TYPE: self.value_type, ATTR_VALUE: value}

    def _turn_off_main(self, value_type=None, value=None):
        """Turn the device off."""
        set_req = self.gateway.const.SetReq
        if value_type is None or value is None:
            _LOGGER.warning(
                '%s: value_type %s, value = %s, '
                'None is not valid argument when setting child value'
                '', self._name, value_type, value)
            return
        self.gateway.set_child_value(
            self.node_id, self.child_id, value_type, value)
        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = False
            self._values[value_type] = (
                STATE_OFF if set_req.V_LIGHT in self._values else value)
            self.update_ha_state()

    def _update_light(self):
        """Update the controller with values from light child."""
        value_type = self.gateway.const.SetReq.V_LIGHT
        if value_type in self._values:
            self._values[value_type] = (
                STATE_ON if int(self._values[value_type]) == 1 else STATE_OFF)
            self._state = self._values[value_type] == STATE_ON

    def _update_dimmer(self):
        """Update the controller with values from dimmer child."""
        set_req = self.gateway.const.SetReq
        value_type = set_req.V_DIMMER
        if value_type in self._values:
            self._brightness = round(255 * int(self._values[value_type]) / 100)
            if self._brightness == 0:
                self._state = False
            if set_req.V_LIGHT not in self._values:
                self._state = self._brightness > 0

    def _update_rgb_or_w(self):
        """Update the controller with values from RGB or RGBW child."""
        set_req = self.gateway.const.SetReq
        value = self._values[self.value_type]
        color_list = rgb_hex_to_rgb_list(value)
        if set_req.V_LIGHT not in self._values and \
                set_req.V_DIMMER not in self._values:
            self._state = max(color_list) > 0
        if len(color_list) > 3:
            self._white = color_list.pop()
        self._rgb = color_list

    def _update_main(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        for value_type, value in child.values.items():
            _LOGGER.debug(
                '%s: value_type %s, value = %s', self._name, value_type, value)
            self._values[value_type] = value


class MySensorsLightDimmer(MySensorsLight):
    """Dimmer child class to MySensorsLight."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        ret = self._turn_off_dimmer()
        ret = self._turn_off_light(
            value_type=ret[ATTR_VALUE_TYPE], value=ret[ATTR_VALUE])
        self._turn_off_main(
            value_type=ret[ATTR_VALUE_TYPE], value=ret[ATTR_VALUE])

    def update(self):
        """Update the controller with the latest value from a sensor."""
        self._update_main()
        self._update_light()
        self._update_dimmer()


class MySensorsLightRGB(MySensorsLight):
    """RGB child class to MySensorsLight."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w('%02x%02x%02x', **kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        ret = self._turn_off_rgb_or_w()
        ret = self._turn_off_dimmer(
            value_type=ret[ATTR_VALUE_TYPE], value=ret[ATTR_VALUE])
        ret = self._turn_off_light(
            value_type=ret[ATTR_VALUE_TYPE], value=ret[ATTR_VALUE])
        self._turn_off_main(
            value_type=ret[ATTR_VALUE_TYPE], value=ret[ATTR_VALUE])

    def update(self):
        """Update the controller with the latest value from a sensor."""
        self._update_main()
        self._update_light()
        self._update_dimmer()
        self._update_rgb_or_w()


class MySensorsLightRGBW(MySensorsLightRGB):
    """RGBW child class to MySensorsLightRGB."""

    def turn_on(self, **kwargs):
        """Turn the device on."""
        self._turn_on_light()
        self._turn_on_dimmer(**kwargs)
        self._turn_on_rgb_and_w('%02x%02x%02x%02x', **kwargs)
