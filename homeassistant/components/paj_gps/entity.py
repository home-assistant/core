"""Base entity class for the PAJ GPS integration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import PajGpsCoordinator


class PajGpsEntity(CoordinatorEntity[PajGpsCoordinator]):
    """Base class for all PAJ GPS entities.

    Populates and caches DeviceInfo eagerly in __init__ so it is ready
    before the entity is registered with Home Assistant.
    """

    _attr_has_entity_name = True

    def __init__(self, coordinator: PajGpsCoordinator, device_id: int) -> None:
        """Initialise the entity and eagerly build DeviceInfo."""
        super().__init__(coordinator)
        self._device_id = device_id
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo | None:
        """Build a DeviceInfo from current coordinator data."""
        device = self.coordinator.data.devices.get(self._device_id)
        if device is None:
            return None

        model = None
        device_models = getattr(device, "device_models", None)
        if device_models and isinstance(device_models[0], dict):
            model = device_models[0].get("model") or None

        return DeviceInfo(
            identifiers={(DOMAIN, f"{self.coordinator.user_id}_{self._device_id}")},
            name=device.name or f"PAJ GPS {self._device_id}",
            manufacturer="PAJ GPS",
            model=model,
        )
