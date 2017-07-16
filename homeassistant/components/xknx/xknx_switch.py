
from homeassistant.components.switch import SwitchDevice


class XKNXSwitch(SwitchDevice):
    """Representation of XKNX switches."""

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
    def name(self):
        return self.device.name


    @property
    def is_on(self):
        """Return true if pin is high/on."""
        return self.device.state


    def turn_on(self):
        """Turn the pin to high/on."""
        self.device.set_on()


    def turn_off(self):
        """Turn the pin to low/off."""
        self.device.set_off()
