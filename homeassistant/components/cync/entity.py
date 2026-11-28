"""Setup for a generic entity type for the Cync integration."""

from datetime import datetime
from typing import override

from pycync.devices import CyncDevice

from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import CyncCoordinator

_ONLINE_GRACE_PERIOD = 90.0


class CyncBaseEntity(CoordinatorEntity[CyncCoordinator]):
    """Generic base entity for Cync devices."""

    _attr_has_entity_name = True
    _seen_online = False
    _grace_expiry_cancel: CALLBACK_TYPE | None = None

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

    @override
    async def async_added_to_hass(self) -> None:
        """Record the initial online state."""
        await super().async_added_to_hass()
        self._track_online_state()

    @callback
    @override
    def _handle_coordinator_update(self) -> None:
        """Debounce transient offline states."""
        self._track_online_state()
        super()._handle_coordinator_update()

    @callback
    def _track_online_state(self) -> None:
        device = (
            self.coordinator.data.get(self._cync_unique_id)
            if self.coordinator.data is not None
            else None
        )
        if device is not None and device.is_online:
            self._seen_online = True
            self._cancel_grace_expiry()
        elif self._seen_online and self._grace_expiry_cancel is None:
            self._seen_online = False
            self._grace_expiry_cancel = async_call_later(
                self.hass, _ONLINE_GRACE_PERIOD, self._async_grace_expired
            )

    @callback
    def _async_grace_expired(self, _now: datetime) -> None:
        """Write state once the offline grace period has elapsed."""
        self._grace_expiry_cancel = None
        self.async_write_ha_state()

    @callback
    def _cancel_grace_expiry(self) -> None:
        if self._grace_expiry_cancel is not None:
            self._grace_expiry_cancel()
            self._grace_expiry_cancel = None

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel any pending grace expiry."""
        self._cancel_grace_expiry()
        await super().async_will_remove_from_hass()

    @property
    @override
    def available(self) -> bool:
        """Determines whether this device is currently available."""
        if not super().available or self.coordinator.data is None:
            return False
        if self._cync_unique_id not in self.coordinator.data:
            return False
        return (
            self.coordinator.data[self._cync_unique_id].is_online
            or self._grace_expiry_cancel is not None
        )
