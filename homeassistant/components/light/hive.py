"""Hive Integration - light."""
import logging
from homeassistant.components.light import (Light, ATTR_BRIGHTNESS,
                                            ATTR_COLOR_TEMP,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_COLOR_TEMP,
                                            SUPPORT_RGB_COLOR)
from homeassistant.loader import get_component

DEPENDENCIES = ['hive']

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_devices,
                   device_list, discovery_info=None):
    """Setup Hive light devices."""
    hive_comp = get_component('hive')

    if len(device_list) > 0:
        for a_device in device_list:
            add_devices([HiveDeviceLight(hass,
                                         hive_comp.HGO,
                                         a_device["Hive_NodeID"],
                                         a_device["Hive_NodeName"],
                                         a_device["HA_DeviceType"],
                                         a_device["Hive_Light_DeviceType"])])


class HiveDeviceLight(Light):
    """Hive Active Light Device."""

    def __init__(self, hass, hivecomponent_hiveobjects, node_id, node_name,
                 device_type, node_device_type):
        """Initialize the Light device."""
        self.h_o = hivecomponent_hiveobjects
        self.node_id = node_id
        self.node_name = node_name
        self.device_type = device_type
        self.node_device_type = node_device_type

        def handle_event(event):
            """Handle the new event."""
            self.schedule_update_ha_state()

        hass.bus.listen('Event_Hive_NewNodeData', handle_event)

    @property
    def name(self):
        """Return the display name of this light."""
        return self.node_name

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        min_color_temp = None
        if self.node_device_type == "tuneablelight" \
                or self.node_device_type == "colourtuneablelight":
            min_color_temp = self.h_o.get_light_min_color_temp(
                self.node_id, self.device_type, self.node_name)

        return min_color_temp

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        max_color_temp = None
        if self.node_device_type == "tuneablelight" \
                or self.node_device_type == "colourtuneablelight":
            max_color_temp = self.h_o.get_light_max_color_temp(
                self.node_id, self.device_type, self.node_name)

        return max_color_temp

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        color_temp = None
        if self.node_device_type == "tuneablelight" \
                or self.node_device_type == "colourtuneablelight":
            color_temp = self.h_o.get_light_color_temp(
                self.node_id, self.device_type, self.node_name)

        return color_temp

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self.h_o.get_light_brightness(self.node_id,
                                             self.device_type,
                                             self.node_name)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.h_o.get_light_state(self.node_id,
                                        self.device_type,
                                        self.node_name)

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs.get(ATTR_BRIGHTNESS)
            percentage_brightness = ((tmp_new_brightness / 255) * 100)
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP in kwargs:
            tmp_new_color_temp = kwargs.get(ATTR_COLOR_TEMP)
            new_color_temp = round(1000000 / tmp_new_color_temp)

        self.h_o.set_light_turn_on(self.node_id,
                                   self.device_type,
                                   self.node_device_type,
                                   self.node_name,
                                   new_brightness,
                                   new_color_temp)

    def turn_off(self):
        """Instruct the light to turn off."""
        self.h_o.set_light_turn_off(self.node_id,
                                    self.device_type,
                                    self.node_device_type,
                                    self.node_name)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = None
        if self.node_device_type == "warmwhitelight":
            supported_features = SUPPORT_BRIGHTNESS
        elif self.node_device_type == "tuneablelight":
            supported_features = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP)
        elif self.node_device_type == "colourtuneablelight":
            supported_features = (
                SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR)

        return supported_features
