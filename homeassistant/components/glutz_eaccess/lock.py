"""Lock platform for the Glutz eAccess integration."""
from __future__ import annotations

import asyncio
from typing import Any

from pyglutz_eaccess import GlutzAuthError, GlutzConnectionError

from homeassistant.components.lock import LockEntity, LockEntityFeature
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import GlutzConfigEntry, GlutzCoordinator

PARALLEL_UPDATES = 0

# Matches the physical door's automatic re-lock time. The API exposes no
# real lock state, so we simulate "unlocked" for this many seconds.
UNLOCK_DURATION = 3


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GlutzConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create a GlutzLock per access point from the coordinator's snapshot."""
    coordinator = entry.runtime_data
    async_add_entities(
        GlutzLock(coordinator, ap) for ap in coordinator.data.values()
    )


class GlutzLock(CoordinatorEntity[GlutzCoordinator], LockEntity):
    """Represents a Glutz access point as a Home Assistant lock entity.

    The door has no state feedback (it re-locks automatically after a few
    seconds), so the state is simulated: unlocked for UNLOCK_DURATION
    seconds, then reverted to locked.
    """

    _attr_has_entity_name = True
    _attr_assumed_state = True
    _attr_name = None
    _attr_translation_key = "access_point"
    _attr_supported_features = LockEntityFeature.OPEN

    def __init__(
        self,
        coordinator: GlutzCoordinator,
        access_point: dict[str, Any],
    ) -> None:
        """Initialize the lock entity for a single access point."""
        super().__init__(coordinator)
        self._access_point_id: str = access_point["accessPointId"]
        location: list[str] = access_point.get("location", [])
        self._device_name = (
            location[-1] if location else f"Door {self._access_point_id}"
        )
        self._attr_unique_id = f"glutz_{self._access_point_id}"
        self._attr_is_locked = True
        self._relock_task: asyncio.Task[None] | None = None

    @property
    def available(self) -> bool:
        """Return whether the access point is still reported by the coordinator."""
        return super().available and self._access_point_id in self.coordinator.data

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info for the access point."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._access_point_id)},
            name=self._device_name,
            manufacturer="Glutz",
        )

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the door and schedule an automatic re-lock."""
        try:
            success = await self.coordinator.api.open_access_point(self._access_point_id)
        except GlutzAuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err
        except GlutzConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_access_point_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="open_access_point_failed",
                translation_placeholders={"access_point_id": self._access_point_id},
            )
        self._attr_is_locked = False
        self.async_write_ha_state()
        if self._relock_task:
            self._relock_task.cancel()
        self._relock_task = self.hass.async_create_task(self._relock())

    async def async_open(self, **kwargs: Any) -> None:
        """Hold the door open indefinitely and cancel any pending auto-relock."""
        try:
            success = await self.coordinator.api.hold_open_access_point(self._access_point_id)
        except GlutzAuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err
        except GlutzConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="hold_open_access_point_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="hold_open_access_point_failed",
                translation_placeholders={"access_point_id": self._access_point_id},
            )
        if self._relock_task:
            self._relock_task.cancel()
            self._relock_task = None
        self._attr_is_locked = False
        self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Force-lock the door and cancel any pending auto-relock."""
        try:
            success = await self.coordinator.api.close_access_point(
                self._access_point_id
            )
        except GlutzAuthError as err:
            self.coordinator.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="auth_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err
        except GlutzConnectionError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="close_access_point_error",
                translation_placeholders={"access_point_id": self._access_point_id},
            ) from err

        if not success:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="close_access_point_failed",
                translation_placeholders={"access_point_id": self._access_point_id},
            )
        if self._relock_task:
            self._relock_task.cancel()
            self._relock_task = None
        self._attr_is_locked = True
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        """Cancel a pending auto-relock when the entity is removed."""
        if self._relock_task:
            self._relock_task.cancel()
            self._relock_task = None

    async def _relock(self) -> None:
        """Revert the entity to the locked state after UNLOCK_DURATION seconds."""
        await asyncio.sleep(UNLOCK_DURATION)
        self._relock_task = None
        self._attr_is_locked = True
        self.async_write_ha_state()
