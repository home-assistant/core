"""
Support for the Hive devices.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.hive/
"""
from homeassistant.components.hive import DATA_HIVE
from homeassistant.components.light import (ATTR_BRIGHTNESS, ATTR_COLOR_TEMP,
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
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_min_colour_temp(self.node_id)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_max_colour_temp(self.node_id)

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        if self.light_device_type == "tuneablelight" \
                or self.light_device_type == "colourtuneablelight":
            return self.session.light.get_color_temp(self.node_id)

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self.session.light.get_brightness(self.node_id)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.session.light.get_state(self.node_id)

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

        if new_brightness is not None:
            self.session.light.set_brightness(self.node_id, new_brightness)
        elif new_color_temp is not None:
            self.session.light.set_colour_temp(self.node_id, new_color_temp)
        else:
            self.session.light.turn_on(self.node_id)

        for entity in self.session.entities:
            entity.handle_update(self.data_updatesource)

    def turn_off(self):
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
        """Update all Node data frome Hive."""
        self.session.core.update_data(self.node_id)
