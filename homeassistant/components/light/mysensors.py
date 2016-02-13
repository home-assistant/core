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
        if float(gateway.version) >= 1.5:
            # Add V_RGBW when rgb_white is implemented in the frontend
            map_sv_types.update({
                pres.S_RGB_LIGHT: [set_req.V_RGB],
            })
            map_sv_types[pres.S_LIGHT].append(set_req.V_STATUS)
            map_sv_types[pres.S_DIMMER].append(set_req.V_PERCENTAGE)

        devices = {}
        gateway.platform_callbacks.append(mysensors.pf_callback_factory(
            map_sv_types, devices, add_devices, MySensorsLight))


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
        self._rgb = None
        self._brightness = None
        self._white = None

    @property
    def should_poll(self):
        """MySensor gateway pushes its state to HA."""
        return False

    @property
    def name(self):
        """The name of this entity."""
        return self._name

    @property
    def brightness(self):
        """Brightness of this light between 0..255."""
        return self._brightness

    @property
    def rgb_color(self):
        """RGB color value [int, int, int]."""
        return self._rgb

    @property
    def rgb_white(self):  # not implemented in the frontend yet
        """White value in RGBW, value between 0..255."""
        return self._white

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
    def is_on(self):
        """True if device is on."""
        return self._state

    def turn_on(self, **kwargs):
        """Turn the device on."""
        set_req = self.gateway.const.SetReq
        rgb = self._rgb
        brightness = self._brightness
        white = self._white

        if set_req.V_LIGHT in self._values and not self._state:
            self.gateway.set_child_value(
                self.node_id, self.child_id, set_req.V_LIGHT, 1)

        if ATTR_BRIGHTNESS in kwargs and set_req.V_DIMMER in self._values and \
                kwargs[ATTR_BRIGHTNESS] != self._brightness:
            brightness = kwargs[ATTR_BRIGHTNESS]
            percent = round(100 * brightness / 255)
            self.gateway.set_child_value(
                self.node_id, self.child_id, set_req.V_DIMMER, percent)

        if float(self.gateway.version) >= 1.5:

            if ATTR_RGB_WHITE in kwargs and \
                    self.value_type in (set_req.V_RGB, set_req.V_RGBW) and \
                    kwargs[ATTR_RGB_WHITE] != self._white:
                white = kwargs[ATTR_RGB_WHITE]

            if ATTR_RGB_COLOR in kwargs and \
                    self.value_type in (set_req.V_RGB, set_req.V_RGBW) and \
                    kwargs[ATTR_RGB_COLOR] != self._rgb:
                rgb = kwargs[ATTR_RGB_COLOR]
                if set_req.V_RGBW == self.value_type:
                    hex_template = '%02x%02x%02x%02x'
                    color_list = rgb.append(white)
                if set_req.V_RGB == self.value_type:
                    hex_template = '%02x%02x%02x'
                    color_list = rgb
                hex_color = hex_template % tuple(color_list)
                self.gateway.set_child_value(
                    self.node_id, self.child_id, self.value_type, hex_color)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = True
            self._rgb = rgb
            self._brightness = brightness
            self._white = white
            self.update_ha_state()

    def turn_off(self, **kwargs):
        """Turn the device off."""
        set_req = self.gateway.const.SetReq
        v_type = set_req.V_LIGHT
        value = 0
        if set_req.V_LIGHT in self._values:
            self._values[set_req.V_LIGHT] = STATE_OFF
        elif set_req.V_DIMMER in self._values:
            v_type = set_req.V_DIMMER
        elif float(self.gateway.version) >= 1.5:
            if set_req.V_RGB in self._values:
                v_type = set_req.V_RGB
                value = '000000'
            elif set_req.V_RGBW in self._values:
                v_type = set_req.V_RGBW
                value = '00000000'
        self.gateway.set_child_value(
            self.node_id, self.child_id, v_type, value)

        if self.gateway.optimistic:
            # optimistically assume that light has changed state
            self._state = False
            self.update_ha_state()

    @property
    def available(self):
        """Return True if entity is available."""
        return self.value_type in self._values

    def update(self):
        """Update the controller with the latest value from a sensor."""
        node = self.gateway.sensors[self.node_id]
        child = node.children[self.child_id]
        set_req = self.gateway.const.SetReq
        self.battery_level = node.battery_level
        for value_type, value in child.values.items():
            _LOGGER.debug(
                "%s: value_type %s, value = %s", self._name, value_type, value)
            if value_type == set_req.V_LIGHT:
                self._values[value_type] = (
                    STATE_ON if int(value) == 1 else STATE_OFF)
                self._state = self._values[value_type] == STATE_ON
            else:
                self._values[value_type] = value
                if value_type == set_req.V_DIMMER:
                    self._brightness = round(
                        255 * int(self._values[value_type]) / 100)
                    if self._brightness == 0:
                        self._state = False
                    if set_req.V_LIGHT not in self._values:
                        self._state = self._brightness > 0
                if float(self.gateway.version) >= 1.5 and \
                        value_type in (set_req.V_RGB, set_req.V_RGBW):
                    # convert hex color string to rgb(w) integer list
                    color_list = [int(value[i:i + len(value) // 3], 16)
                                  for i in range(0,
                                                 len(value),
                                                 len(value) // 3)]
                    if len(color_list) > 3:
                        self._white = color_list.pop()
                    self._rgb = color_list
                    if set_req.V_LIGHT not in self._values or \
                            set_req.V_DIMMER not in self._values:
                        self._state = max(color_list) > 0
