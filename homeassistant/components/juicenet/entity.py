"""Adapter to wrap the pyjuicenet api for home assistant."""

from pyjuicenet import Charger

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class JuiceNetDevice(CoordinatorEntity):
    """Represent a base JuiceNet device."""

    def __init__(
        self, device: Charger, key: str, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.device = device
        self.key = key

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.device.id}-{self.key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information about this JuiceNet Device."""
        return DeviceInfo(
            configuration_url=f"https://home.juice.net/Portal/Details?unitID={self.device.id}",
            identifiers={(DOMAIN, self.device.id)},
            manufacturer="JuiceNet",
            name=self.device.name,
        )
