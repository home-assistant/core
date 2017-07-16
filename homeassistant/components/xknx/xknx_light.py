from homeassistant.components.light import ATTR_BRIGHTNESS, \
    SUPPORT_BRIGHTNESS, Light

class XKNXLight(Light):
    """Representation of XKNX lights."""

    def __init__(self, hass, device):
        self.device = device
        self.hass = hass
        self.register_callbacks()


    def register_callbacks(self):
        def after_update_callback(device):
            # pylint: disable=unused-argument
            self.update_ha()
        self.device.register_device_updated_cb(after_update_callback)


    def update_ha(self):
        self.hass.async_add_job(self.async_update_ha_state())


    @property
    def should_poll(self):
        """No polling needed for a demo light."""
        return False


    @property
    def name(self):
        """Return the name of the light if any."""
        return self.device.name

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        return self.device.brightness \
            if self.device.supports_dimming else \
            None

    @property
    def xy_color(self):
        """Return the XY color value [float, float]."""
        return None

    @property
    def rgb_color(self):
        """Return the RBG color value."""
        return None

    @property
    def color_temp(self):
        """Return the CT color temperature."""
        return None

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_dimming:
            flags |= SUPPORT_BRIGHTNESS
        return flags


    def turn_on(self, **kwargs):
        """Turn the light on."""
        if ATTR_BRIGHTNESS in kwargs and self.device.supports_dimming:
            self.device.set_brightness(int(kwargs[ATTR_BRIGHTNESS]))
        else:
            self.device.set_on()
        self.update_ha()

    def turn_off(self, **kwargs):
        """Turn the light off."""
        self.device.set_off()
        self.update_ha()
