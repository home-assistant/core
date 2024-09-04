"""YoLink Lock V1/V2."""

from __future__ import annotations

from typing import Any

from yolink.client_request import ClientRequest
from yolink.const import ATTR_DEVICE_LOCK, ATTR_DEVICE_LOCK_V2

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink lock from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id].device_coordinators
    entities = [
        YoLinkLockEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type
        in [ATTR_DEVICE_LOCK, ATTR_DEVICE_LOCK_V2]
    ]
    async_add_entities(entities)


class YoLinkLockEntity(YoLinkEntity, LockEntity):
    """YoLink Lock Entity."""

    _attr_name = None

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Lock."""
        super().__init__(config_entry, coordinator)
        self._attr_unique_id = f"{coordinator.device.device_id}_lock_state"

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        state_value = state.get("state")
        if self.coordinator.device.device_type == ATTR_DEVICE_LOCK_V2:
            self._attr_is_locked = (
                state_value["lock"] == "locked" if state_value is not None else None
            )
        else:
            self._attr_is_locked = (
                state_value == "locked" if state_value is not None else None
            )
        self.async_write_ha_state()

    async def call_lock_state_change(self, state: str) -> None:
        """Call setState api to change lock state."""
        if self.coordinator.device.device_type == ATTR_DEVICE_LOCK_V2:
            await self.call_device(
                ClientRequest("setState", {"state": {"lock": state}})
            )
        else:
            await self.call_device(ClientRequest("setState", {"state": state}))
        self._attr_is_locked = state == "lock"
        self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock device."""
        state_param = (
            "locked"
            if self.coordinator.device.device_type == ATTR_DEVICE_LOCK_V2
            else "lock"
        )
        await self.call_lock_state_change(state_param)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock device."""
        state_param = (
            "unlocked"
            if self.coordinator.device.device_type == ATTR_DEVICE_LOCK_V2
            else "unlock"
        )
        await self.call_lock_state_change(state_param)
