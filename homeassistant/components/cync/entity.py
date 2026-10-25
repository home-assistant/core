"""Setup for a generic entity type for the Cync integration."""

import time
from typing import override

from pycync.devices import CyncDevice

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CyncCoordinator

_ONLINE_GRACE_PERIOD = 90.0


class CyncBaseEntity(CoordinatorEntity[CyncCoordinator]):
    """Generic base entity for Cync devices."""

    _attr_has_entity_name = True
    _last_online_time: float | None = None

    def __init__(
        self,
        device: CyncDevice,
        coordinator: CyncCoordinator,
        room_name: str | None = None,
        *,
        unique_id: str | None = None,
    ) -> None:
        """Pass coordinator to CoordinatorEntity."""
        super().__init__(coordinator)

        self._cync_unique_id = device.unique_id
        self._attr_unique_id = device.unique_id if unique_id is None else unique_id

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._attr_unique_id)},
            manufacturer="GE Lighting",
            name=device.name,
            suggested_area=room_name,
        )

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Track last-online time to debounce transient offline states."""
        if (
            self.coordinator.data is not None
            and self._cync_unique_id in self.coordinator.data
            and self.coordinator.data[self._cync_unique_id].is_online
        ):
            self._last_online_time = time.monotonic()
        super()._handle_coordinator_update()

    @property
    @override
    def available(self) -> bool:
        """Determines whether this device is currently available."""
        if not super().available or self.coordinator.data is None:
            return False
        if self._cync_unique_id not in self.coordinator.data:
            return False
        if self.coordinator.data[self._cync_unique_id].is_online:
            return True
        if self._last_online_time is not None:
            return time.monotonic() - self._last_online_time < _ONLINE_GRACE_PERIOD
        return False
