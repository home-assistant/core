"""Base Entity for JustNimbus sensors."""
from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import JustNimbusCoordinator


class JustNimbusEntity(
    CoordinatorEntity[JustNimbusCoordinator],
):
    """Defines a base JustNimbus entity."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        device_id: str,
        coordinator: JustNimbusCoordinator,
    ) -> None:
        """Initialize the JustNimbus entity."""
        super().__init__(coordinator=coordinator)
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, device_id)},
            name="JustNimbus Sensor",
            manufacturer="JustNimbus",
        )

    @property
    def available(self) -> bool:
        """Return device availability."""
        return super().available and self.coordinator.data is not None
