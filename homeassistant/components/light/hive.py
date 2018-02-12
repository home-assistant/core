"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hive/
"""
import colorsys
from homeassistant.components.hive import DATA_HIVE
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_COLOR_TEMP,
                                            ATTR_RGB_COLOR,
                                            SUPPORT_BRIGHTNESS,
                                            SUPPORT_COLOR_TEMP,
                                            SUPPORT_RGB_COLOR, Light)

DEPENDENCIES = ['hive']


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up Hive light devices."""
    if discovery_info is None:
        return
    session = hass.data.get(DATA_HIVE)

    add_devices([HiveDeviceLight(session, discovery_info)])


class HiveDeviceLight(Light):
    """Hive Active Light Device."""

    def __init__(self, hivesession, hivedevice):
        """Initialize the Light device."""
        self.node_id = hivedevice["Hive_NodeID"]
        self.node_name = hivedevice["Hive_NodeName"]
        self.device_type = hivedevice["HA_DeviceType"]
        self.light_device_type = hivedevice["Hive_Light_DeviceType"]
        self.session = hivesession
        self.data_updatesource = '{}.{}'.format(self.device_type,
                                                self.node_id)
        self.session.entities.append(self)

    def handle_update(self, updatesource):
        """Handle the new update request."""
        if '{}.{}'.format(self.device_type, self.node_id) not in updatesource:
            self.schedule_update_ha_state()

    @property
    def name(self):
        """Return the display name of this light."""
        return self.node_name

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self.session.light.get_brightness(self.node_id)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_min_color_temp(self.node_id)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_max_color_temp(self.node_id)

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_color_temp(self.node_id)

    @property
    def rgb_color(self) -> tuple:
        """Return the RBG color value."""
        if self.light_device_type == "colourtuneablelight":
            return self.session.light.get_color(self.node_id)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.session.light.get_state(self.node_id)

    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        new_color = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs.get(ATTR_BRIGHTNESS)
            percentage_brightness = ((tmp_new_brightness / 255) * 100)
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP in kwargs:
            tmp_new_color_temp = kwargs.get(ATTR_COLOR_TEMP)
            new_color_temp = round(1000000 / tmp_new_color_temp)
        if ATTR_RGB_COLOR in kwargs:
            get_new_color = kwargs.get(ATTR_RGB_COLOR)
            tmp_new_color = colorsys.rgb_to_hsv(get_new_color[0],
                                                get_new_color[1],
                                                get_new_color[2])
            hue = int(round(tmp_new_color[0] * 360))
            saturation = int(round(tmp_new_color[1] * 100))
            value = int(round((tmp_new_color[2] / 255) * 100))
            new_color = (hue, saturation, value)

        self.session.light.turn_on(self.node_id, self.light_device_type,
                                   new_brightness, new_color_temp,
                                   new_color)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.session.light.turn_off(self.node_id)
        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = None
        if self.light_device_type == "warmwhitelight":
            supported_features = SUPPORT_BRIGHTNESS
        elif self.light_device_type == "tuneablelight":
            supported_features = (SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP)
        elif self.light_device_type == "colourtuneablelight":
            supported_features = (
                SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_RGB_COLOR)

        return supported_features

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
