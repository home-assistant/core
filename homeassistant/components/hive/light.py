"""Support for the Hive lights."""
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP,
    ATTR_HS_COLOR,
    SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR,
    SUPPORT_COLOR_TEMP,
    LightEntity,
)
import homeassistant.util.color as color_util

from . import DATA_HIVE, DOMAIN, HiveEntity, refresh_system


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up Hive light devices."""
    if discovery_info is None:
        return

    session = hass.data.get(DATA_HIVE)
    devs = []
    for dev in discovery_info:
        devs.append(HiveDeviceLight(session, dev))
    add_entities(devs)


class HiveDeviceLight(HiveEntity, LightEntity):
    """Hive Active Light Device."""

    def __init__(self, hive_session, hive_device):
        """Initialize the Light device."""
        super().__init__(hive_session, hive_device)
        self.light_device_type = hive_device["Hive_Light_DeviceType"]

    @property
    def unique_id(self):
        """Return unique ID of entity."""
        return self._unique_id

    @property
    def device_info(self):
        """Return device information."""
        return {"identifiers": {(DOMAIN, self.unique_id)}, "name": self.name}

    @property
    def name(self):
        """Return the display name of this light."""
        return self.node_name

    @property
    def device_state_attributes(self):
        """Show Device Attributes."""
        return self.attributes

    @property
    def brightness(self):
        """Brightness of the light (an integer in the range 1-255)."""
        return self.session.light.get_brightness(self.node_id)

    @property
    def min_mireds(self):
        """Return the coldest color_temp that this light supports."""
        if (
            self.light_device_type == "tuneablelight"
            or self.light_device_type == "colourtuneablelight"
        ):
            return self.session.light.get_min_color_temp(self.node_id)

    @property
    def max_mireds(self):
        """Return the warmest color_temp that this light supports."""
        if (
            self.light_device_type == "tuneablelight"
            or self.light_device_type == "colourtuneablelight"
        ):
            return self.session.light.get_max_color_temp(self.node_id)

    @property
    def color_temp(self):
        """Return the CT color value in mireds."""
        if (
            self.light_device_type == "tuneablelight"
            or self.light_device_type == "colourtuneablelight"
        ):
            return self.session.light.get_color_temp(self.node_id)

    @property
    def hs_color(self) -> tuple:
        """Return the hs color value."""
        if self.light_device_type == "colourtuneablelight":
            rgb = self.session.light.get_color(self.node_id)
            return color_util.color_RGB_to_hs(*rgb)

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.session.light.get_state(self.node_id)

    @refresh_system
    def turn_on(self, **kwargs):
        """Instruct the light to turn on."""
        new_brightness = None
        new_color_temp = None
        new_color = None
        if ATTR_BRIGHTNESS in kwargs:
            tmp_new_brightness = kwargs.get(ATTR_BRIGHTNESS)
            percentage_brightness = (tmp_new_brightness / 255) * 100
            new_brightness = int(round(percentage_brightness / 5.0) * 5.0)
            if new_brightness == 0:
                new_brightness = 5
        if ATTR_COLOR_TEMP in kwargs:
            tmp_new_color_temp = kwargs.get(ATTR_COLOR_TEMP)
            new_color_temp = round(1000000 / tmp_new_color_temp)
        if ATTR_HS_COLOR in kwargs:
            get_new_color = kwargs.get(ATTR_HS_COLOR)
            hue = int(get_new_color[0])
            saturation = int(get_new_color[1])
            new_color = (hue, saturation, 100)

        self.session.light.turn_on(
            self.node_id,
            self.light_device_type,
            new_brightness,
            new_color_temp,
            new_color,
        )

    @refresh_system
    def turn_off(self, **kwargs):
        """Instruct the light to turn off."""
        self.session.light.turn_off(self.node_id)

    @property
    def supported_features(self):
        """Flag supported features."""
        supported_features = None
        if self.light_device_type == "warmwhitelight":
            supported_features = SUPPORT_BRIGHTNESS
        elif self.light_device_type == "tuneablelight":
            supported_features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP
        elif self.light_device_type == "colourtuneablelight":
            supported_features = SUPPORT_BRIGHTNESS | SUPPORT_COLOR_TEMP | SUPPORT_COLOR

        return supported_features

    def update(self):
        """Update all Node data from Hive."""
        self.session.core.update_data(self.node_id)
        self.attributes = self.session.attributes.state_attributes(self.node_id)
