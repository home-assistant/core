"""Base entity class for the PAJ GPS integration."""

from typing import override

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import Device, PajGpsCoordinator


class PajGpsEntity(CoordinatorEntity[PajGpsCoordinator]):
    """Base class for all PAJ GPS entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: PajGpsCoordinator, device_id: int) -> None:
        """Initialize the entity and build DeviceInfo."""
        super().__init__(coordinator)
        self._device_id = device_id

        model = None
        device_models = self.device.device_models
        if device_models:
            model = device_models[0].model
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{coordinator.user_id}_{device_id}")},
            name=self.device.name or f"PAJ GPS {device_id}",
            manufacturer="PAJ GPS",
            model=model,
        )

    @property
    @override
    def available(self) -> bool:
        """Return False when the device has been removed from the account."""
        return super().available and self._device_id in self.coordinator.data.devices

    @property
    def device(self) -> Device:
        """Return the device from coordinator data."""
        return self.coordinator.data.devices[self._device_id]
