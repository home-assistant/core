"""
homeassistant.components.light.mysensors.

~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Support for MySensors lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.mysensors.html
"""
import logging

from homeassistant.components.light import (
    Light, ATTR_BRIGHTNESS, ATTR_RGB_COLOR)

from homeassistant.util.color import (
    rgb_hex_to_list)

from homeassistant.const import (
    ATTR_BATTERY_LEVEL,
    STATE_ON, STATE_OFF)

import homeassistant.components.mysensors as mysensors

_LOGGER = logging.getLogger(__name__)
ATTR_RGB_WHITE = 'rgb_white'


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
            pres.S_LIGHT: [set_req.V_LIGHT],
            pres.S_DIMMER: [set_req.V_DIMMER],
        }
        device_class_map = {
            pres.S_LIGHT: MySensorsLightLight,
            pres.S_DIMMER: MySensorsLightDimmer,
        }
        if float(gateway.version) >= 1.5:
            # Add V_RGBW when rgb_white is implemented in the frontend
            map_sv_types.update({
                pres.S_RGB_LIGHT: [set_req.V_RGB],
            })
            map_sv_types[pres.S_LIGHT].append(set_req.V_STATUS)
            map_sv_types[pres.S_DIMMER].append(set_req.V_PERCENTAGE)
            device_class_map.update({
                pres.S_RGB_LIGHT: MySensorsLightRGB,
            })
        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, device_class_map))


class MySensorsLight(Light):
    """Represent the value of a MySensors child node."""

    # pylint: disable=too-many-arguments,too-many-instance-attributes

    def __init__(self, gateway, node_id, child_id, name, value_type):
        """Setup instance attributes."""
        self.gateway = gateway
        self.node_id = node_id
        self.child_id = child_id
        self._name = name
        self.value_type = value_type
        self.battery_level = 0
        self._values = {}
        self._state = None

    @property
    def should_poll(self):
        """MySensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def device_state_attributes(self):
        """Return device specific state attributes."""
        device_attr = {
            mysensors.ATTR_PORT: self.gateway.port,
            mysensors.ATTR_NODE_ID: self.node_id,
            mysensors.ATTR_CHILD_ID: self.child_id,
            ATTR_BATTERY_LEVEL: self.battery_level,
        }
        for value_type, value in self._values.items():
            device_attr[self.gateway.const.SetReq(value_type).name] = value
        return device_attr

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    @property
    def is_on(self):
        """True if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        value_type = kwargs.get('value_type')
        value = kwargs.get('value')
        if value_type is not None and value is not None:
            self.gateway.set_child_value(
                self.node_id, self.child_id, value_type, value)
        else:
            _LOGGER.warning(
                '%s: value_type %s, value = %s, '
                'None is not valid argument when setting child value'
                '', self._name, value_type, value)
        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = False
            self.update_ha_state()

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        self.battery_level = node.battery_level
        for value_type, value in child.values.items():
            _LOGGER.debug(
                '%s: value_type %s, value = %s', self._name, value_type, value)
            self._values[value_type] = value


class MySensorsLightLight(MySensorsLight):
    """Light child class to MySensorsLight."""

    def __init__(self, *args):
        """Setup instance attributes."""
        super().__init__(*args)

    def turn_on(self, **kwargs):
        """Turn the device on."""
        set_req = self.gateway.const.SetReq

        if not self._state:
            self.gateway.set_child_value(
                self.node_id, self.child_id, set_req.V_LIGHT, 1)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = True
        super().turn_on(**kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        set_req = self.gateway.const.SetReq
        value_type = kwargs.get('value_type')
        value = kwargs.get('value')
        value_type = (
            set_req.V_LIGHT
            if set_req.V_LIGHT in self._values else value_type)
        value = 0 if set_req.V_LIGHT in self._values else value
        super().turn_off(value_type=value_type, value=value)

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        value_type = self.gateway.const.SetReq.V_LIGHT
        if value_type in self._values:
            self._values[value_type] = (
                STATE_ON if int(self._values[value_type]) == 1 else STATE_OFF)
            self._state = self._values[value_type] == STATE_ON


class MySensorsLightDimmer(MySensorsLightLight):
    """Dimmer child class to MySensorsLight."""

    def __init__(self, *args):
        """Setup instance attributes."""
        self._brightness = None
        super().__init__(*args)

    @property
    def brightness(self):
        """Brightness of this light between 0..255."""
        return self._brightness

    def turn_on(self, **kwargs):
        """Turn the device on."""
        set_req = self.gateway.const.SetReq
        brightness = self._brightness

        if ATTR_BRIGHTNESS in kwargs and \
                kwargs[ATTR_BRIGHTNESS] != self._brightness:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent = round(100 * brightness / 255)
            self.gateway.set_child_value(
                self.node_id, self.child_id, set_req.V_DIMMER, percent)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._brightness = brightness
        super().turn_on(**kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        set_req = self.gateway.const.SetReq
        value_type = kwargs.get('value_type')
        value = kwargs.get('value')
        value_type = (
            set_req.V_DIMMER
            if set_req.V_DIMMER in self._values else value_type)
        value = 0 if set_req.V_DIMMER in self._values else value
        super().turn_off(value_type=value_type, value=value)

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        set_req = self.gateway.const.SetReq
        value_type = set_req.V_DIMMER
        if value_type in self._values:
            self._brightness = round(255 * int(self._values[value_type]) / 100)
            if self._brightness == 0:
                self._state = False
            if set_req.V_LIGHT not in self._values:
                self._state = self._brightness > 0


class MySensorsLightRGB(MySensorsLightDimmer):
    """RGB child class to MySensorsLight."""

    def __init__(self, *args):
        """Setup instance attributes."""
        self._rgb = None
        super().__init__(*args)

    @property
    def rgb_color(self):
        """RGB color value [int, int, int]."""
        return self._rgb

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rgb = self._rgb
        if ATTR_RGB_COLOR in kwargs and kwargs[ATTR_RGB_COLOR] != self._rgb:
            rgb = kwargs[ATTR_RGB_COLOR]
            hex_color = '%02x%02x%02x' % tuple(rgb)
            self.gateway.set_child_value(
                self.node_id, self.child_id, self.value_type, hex_color)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._rgb = rgb
        super().turn_on(**kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        value_type = None
        value = None
        if float(self.gateway.version) >= 1.5:
            value_type = self.gateway.const.SetReq.V_RGB
            value = '000000'
        super().turn_off(value_type=value_type, value=value)

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        set_req = self.gateway.const.SetReq
        if float(self.gateway.version) >= 1.5 and \
                set_req.V_RGB in self._values:
            value = self._values[set_req.V_RGB]
            self._rgb = rgb_hex_to_list(value)
            if set_req.V_LIGHT not in self._values and \
                    set_req.V_DIMMER not in self._values:
                self._state = max(self._rgb) > 0


class MySensorsLightRGBW(MySensorsLightDimmer):
    """RGBW child class to MySensorsLight."""

    def __init__(self, *args):
        """Setup instance attributes."""
        self._rgb = None
        self._white = None
        super().__init__(*args)

    @property
    def rgb_color(self):
        """RGB color value [int, int, int]."""
        return self._rgb

    @property
    def rgb_white(self):  # not implemented in the frontend yet
        """White value in RGBW, value between 0..255."""
        return self._white

    def turn_on(self, **kwargs):
        """Turn the device on."""
        rgb = self._rgb
        white = self._white

        if float(self.gateway.version) >= 1.5:

            if ATTR_RGB_WHITE in kwargs and \
                    kwargs[ATTR_RGB_WHITE] != self._white:
                white = kwargs[ATTR_RGB_WHITE]

            if ATTR_RGB_COLOR in kwargs and \
                    kwargs[ATTR_RGB_COLOR] != self._rgb:
                rgb = kwargs[ATTR_RGB_COLOR]
                if white is not None:
                    rgb.append(white)
                hex_color = '%02x%02x%02x%02x' % tuple(rgb)
                self.gateway.set_child_value(
                    self.node_id, self.child_id, self.value_type, hex_color)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._rgb = rgb
            self._white = white
        super().turn_on(**kwargs)

    def turn_off(self, **kwargs):
        """Turn the device off."""
        value_type = None
        value = None
        if float(self.gateway.version) >= 1.5:
            value_type = self.gateway.const.SetReq.V_RGBW
            value = '00000000'
        super().turn_off(value_type=value_type, value=value)

    def update(self):
        """Update the controller with the latest value from a sensor."""
        super().update()
        set_req = self.gateway.const.SetReq
        if float(self.gateway.version) >= 1.5 and \
                set_req.V_RGBW in self._values:
            value = self._values[set_req.V_RGBW]
            color_list = rgb_hex_to_list(value)
            if set_req.V_LIGHT not in self._values and \
                    set_req.V_DIMMER not in self._values:
                self._state = max(color_list) > 0
            if len(color_list) > 3:
                self._white = color_list.pop()
            self._rgb = color_list
