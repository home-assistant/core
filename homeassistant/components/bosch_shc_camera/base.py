"""Shared HA entity base for all Bosch camera entity platforms.

Provides the common __init__ (cam metadata) and device_info property that
is repeated across number.py (Gen1 + Gen2), button.py, and update.py.
"""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import BoschCameraCoordinator
from .models import get_display_name


class _BoschEntityBase(CoordinatorEntity[BoschCameraCoordinator]):
    """Common init + device_info for all Bosch camera entities.

    Subclass alongside the appropriate HA entity mixin
    (NumberEntity, ButtonEntity, UpdateEntity …) and call
    super().__init__(coordinator, cam_id, entry) from the subclass __init__.
    """

    def __init__(
        self, coordinator: BoschCameraCoordinator, cam_id: str, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._cam_id = cam_id
        self._entry = entry
        info: dict[str, Any] = coordinator.data.get(cam_id, {}).get("info", {})
        self._cam_title: str = info.get("title", cam_id)
        self._model: str = info.get("hardwareVersion", "CAMERA")
        self._model_name: str = get_display_name(self._model)
        self._fw: str = info.get("firmwareVersion", "")
        self._mac: str = info.get("macAddress", "")

    @property
    def device_info(self) -> dict[str, Any]:
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Bosch {self._cam_title}",
            "manufacturer": "Bosch",
            "model": self._model_name,
            "sw_version": self._fw,
            "connections": {("mac", self._mac)} if self._mac else set(),
        }
