"""The Control4 integration."""

from __future__ import annotations

from typing import Any

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from . import Control4RuntimeData
from .const import DOMAIN


class Control4Entity(CoordinatorEntity[Any]):
    """Base entity for Control4."""

    def __init__(
        self,
        runtime_data: Control4RuntimeData,
        coordinator: DataUpdateCoordinator[Any],
        name: str | None,
        idx: int,
        device_name: str | None,
        device_manufacturer: str | None,
        device_model: str | None,
        device_id: int,
    ) -> None:
        """Initialize a Control4 entity."""
        super().__init__(coordinator)
        self.runtime_data = runtime_data
        self._attr_name = name
        self._attr_unique_id = str(idx)
        self._idx = idx
        self._controller_unique_id = runtime_data.controller_unique_id
        self._device_name = device_name
        self._device_manufacturer = device_manufacturer
        self._device_model = device_model
        self._device_id = device_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return info of parent Control4 device of entity."""
        return DeviceInfo(
            identifiers={(DOMAIN, str(self._device_id))},
            manufacturer=self._device_manufacturer,
            model=self._device_model,
            name=self._device_name,
            via_device=(DOMAIN, self._controller_unique_id),
        )
