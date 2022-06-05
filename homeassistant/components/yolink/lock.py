"""YoLink Lock."""
from __future__ import annotations

from typing import Any

from yolink.exception import YoLinkAuthFailError, YoLinkClientError

from homeassistant.components.lock import LockEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_COORDINATORS, ATTR_DEVICE_LOCK, DOMAIN
from .coordinator import YoLinkCoordinator
from .entity import YoLinkEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up YoLink Sensor from a config entry."""
    device_coordinators = hass.data[DOMAIN][config_entry.entry_id][ATTR_COORDINATORS]
    entities = [
        YoLinkLockEntity(config_entry, device_coordinator)
        for device_coordinator in device_coordinators.values()
        if device_coordinator.device.device_type == ATTR_DEVICE_LOCK
    ]
    async_add_entities(entities)


class YoLinkLockEntity(YoLinkEntity, LockEntity):
    """YoLink Lock Entity."""

    def __init__(
        self,
        config_entry: ConfigEntry,
        coordinator: YoLinkCoordinator,
    ) -> None:
        """Init YoLink Lock."""
        super().__init__(coordinator)
        self.config_entry = config_entry
        self._attr_unique_id = f"{coordinator.device.device_id}_lock_state"
        self._attr_name = f"{coordinator.device.device_name}(LockState)"

    @callback
    def update_entity_state(self, state: dict[str, Any]) -> None:
        """Update HA Entity State."""
        state_value = state.get("state")
        self._attr_is_locked = (
            state_value == "locked" if state_value is not None else None
        )
        self.async_write_ha_state()

    async def call_lock_state_change(self, state: str) -> None:
        """Call setState api to change lock state."""
        try:
            # call_device_http_api will check result, fail by raise YoLinkClientError
            await self.coordinator.device.call_device_http_api(
                "setState", {"state": state}
            )
        except YoLinkAuthFailError as yl_auth_err:
            self.config_entry.async_start_reauth(self.hass)
            raise HomeAssistantError(yl_auth_err) from yl_auth_err
        except YoLinkClientError as yl_client_err:
            self.coordinator.last_update_success = False
            raise HomeAssistantError(yl_client_err) from yl_client_err
        self._attr_is_locked = state == "lock"
        self.async_write_ha_state()

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock device."""
        await self.call_lock_state_change("lock")

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock device."""
        await self.call_lock_state_change("unlock")
