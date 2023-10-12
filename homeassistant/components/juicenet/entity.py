"""Adapter to wrap the pyjuicenet api for home assistant."""

from pyjuicenet import Charger

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import DOMAIN


class JuiceNetDevice(CoordinatorEntity):
    """Represent a base JuiceNet device."""

    _attr_has_entity_name = True

    def __init__(
        self, device: Charger, key: str, coordinator: DataUpdateCoordinator
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator)
        self.device = device
        self.key = key
        self._attr_unique_id = f"{device.id}-{key}"
        self._attr_device_info = DeviceInfo(
            configuration_url=(
                f"https://home.juice.net/Portal/Details?unitID={device.id}"
            ),
            identifiers={(DOMAIN, device.id)},
            manufacturer="JuiceNet",
            name=device.name,
        )
