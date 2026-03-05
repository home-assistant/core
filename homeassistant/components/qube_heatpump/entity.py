"""Base entity for Qube Heat Pump."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import QubeCoordinator

if TYPE_CHECKING:
    from .hub import QubeHub


class QubeEntity(CoordinatorEntity[QubeCoordinator]):
    """Base entity for Qube Heat Pump."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: QubeCoordinator,
        hub: QubeHub,
        version: str,
        device_name: str,
    ) -> None:
        """Initialize the base entity."""
        super().__init__(coordinator)
        self._hub = hub
        self._version = version
        self._device_name = device_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, f"{self._hub.host}:{self._hub.unit}")},
            name=self._device_name,
            manufacturer="Qube",
            model="Heat Pump",
            sw_version=self._version,
        )
