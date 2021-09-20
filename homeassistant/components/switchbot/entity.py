"""An abstract class common to all Switchbot entities."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.entity import DeviceInfo, Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MANUFACTURER
from .coordinator import SwitchbotDataUpdateCoordinator


class SwitchbotEntity(CoordinatorEntity, Entity):
    """Generic entity encapsulating common features of Switchbot device."""

    def __init__(
        self,
        coordinator: SwitchbotDataUpdateCoordinator,
        idx: str | None,
        mac: str,
        name: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._last_run_success: bool | None = None
        self._idx = idx
        self._mac = mac
        self._attr_name = name
        self._attr_device_info: DeviceInfo = {
            "connections": {(dr.CONNECTION_NETWORK_MAC, self._mac)},
            "name": self._attr_name,
            "model": self.data["modelName"],
            "manufacturer": MANUFACTURER,
        }

    @property
    def data(self) -> dict[str, Any]:
        """Return coordinator data for this entity."""
        return self.coordinator.data[self._idx]

    @property
    def extra_state_attributes(self) -> Mapping[Any, Any]:
        """Return the state attributes."""
        return {"last_run_success": self._last_run_success, "mac_address": self._mac}
