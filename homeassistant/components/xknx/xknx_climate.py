from homeassistant.components.climate import ClimateDevice
from homeassistant.const import TEMP_CELSIUS, ATTR_TEMPERATURE

class XKNXClimate(ClimateDevice):
    def __init__(self, hass, device):
        self.device = device
        self.hass = hass
        self.register_callbacks()

        self._unit_of_measurement = TEMP_CELSIUS
        self._away = False  # not yet supported
        self._is_fan_on = False  # not yet supported


    def register_callbacks(self):
        def after_update_callback(device):
            # pylint: disable=unused-argument
            self.update_ha()
        self.device.register_device_updated_cb(after_update_callback)

    def update_ha(self):
        self.hass.async_add_job(self.async_update_ha_state())



    @property
    def should_poll(self):
        """Polling not needed """
        return False


    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement


    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self.device.temperature


    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self.device.setpoint


    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None:
            return

        self.device.setpoint = temperature

        #TODO Sent to KNX bus

        self.update_ha()


    def set_operation_mode(self, operation_mode):
        """Set operation mode."""
        raise NotImplementedError()


    @property
    def name(self):
        return self.device.name
