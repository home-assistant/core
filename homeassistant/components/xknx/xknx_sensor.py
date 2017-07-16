
from homeassistant.helpers.entity import Entity

class XKNXSensor(Entity):

    def __init__(self, hass, device):
        self.device = device
        self.hass = hass
        self.register_callbacks()


    @property
    def should_poll(self):
        """No polling needed for a demo sensor."""
        return False


    def register_callbacks(self):
        def after_update_callback(device):
            # pylint: disable=unused-argument
            self.update_ha()
        self.device.register_device_updated_cb(after_update_callback)


    def update_ha(self):
        self.hass.async_add_job(self.async_update_ha_state())


    @property
    def name(self):
        """Return the name of the light if any."""
        return self.device.name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self.device.resolve_state()

    @property
    def unit_of_measurement(self):
        """Return the unit this state is expressed in."""
        return self.device.unit_of_measurement()

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        #return {
        #    "FNORD": "FNORD",
        #}
        return None
