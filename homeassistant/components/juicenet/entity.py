"""Adapter to wrap the pyjuicenet api for home assistant."""

from homeassistant.helpers.entity import DeviceInfo
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
    def device_info(self) -> DeviceInfo:
        """Return device information about this JuiceNet Device."""
        return DeviceInfo(
            configuration_url=f"https://home.juice.net/Portal/Details?unitID={self.device.id}",
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="JuiceNet",
            name=self.device.name,
        )
