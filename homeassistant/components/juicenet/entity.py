"""Adapter to wrap the pyjuicenet api for home assistant."""

from homeassistant.helpers.entity import Entity

from .const import DOMAIN


class JuiceNetDevice(Entity):
    """Represent a base JuiceNet device."""

    def __init__(self, device, sensor_type, hass):
        """Initialise the sensor."""
        self.hass = hass
        self.device = device
        self.type = sensor_type

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name()

    def update(self):
        """Update state of the device."""
        self.device.update_state()

    @property
    def _token(self):
        """Return the device API token."""
        return self.device.token()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device.id()}-{self.type}"

    @property
    def device_info(self):
        """Return device information about this JuiceNet Device."""
        return {
            "identifiers": {(DOMAIN, self.device.id())},
            "name": self.device.name(),
            "manufacturer": "JuiceNet",
        }
