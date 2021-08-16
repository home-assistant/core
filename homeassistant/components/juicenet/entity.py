"""Adapter to wrap the pyjuicenet api for home assistant."""

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class JuiceNetDevice(CoordinatorEntity):
    """Represent a base JuiceNet device."""

    def __init__(self, device, sensor_type, coordinator):
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.device = device
        self.type = sensor_type

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device.id}-{self.type}"

    @property
    def device_info(self):
        """Return device information about this JuiceNet Device."""
        return {
            "identifiers": {(DOMAIN, self.device.id)},
            "name": self.device.name,
            "manufacturer": "JuiceNet",
        }
