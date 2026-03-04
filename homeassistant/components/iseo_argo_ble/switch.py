"""ISEO BLE Lock — per-user enable/disable switch entities."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from iseo_argo_ble import IseoAuthError, IseoConnectionError, UserEntry
from iseo_argo_ble.client import (
    USER_TYPE_ACCOUNT,
    USER_TYPE_BT,
    USER_TYPE_FINGERPRINT,
    USER_TYPE_INVITATION,
    USER_TYPE_PIN,
    USER_TYPE_RFID,
)

from .const import (
    CONF_ADDRESS,
    CONF_ADMIN_PRIV_SCALAR,
    CONF_ADMIN_UUID,
    CONF_UUID,
    DOMAIN,
)
from .coordinator import IseoLogCoordinator

_LOGGER = logging.getLogger(__name__)

_USER_TYPE_LABELS: dict[int, str] = {
    USER_TYPE_RFID: "RFID",
    USER_TYPE_BT: "Bluetooth",
    USER_TYPE_PIN: "PIN",
    USER_TYPE_INVITATION: "Invitation",
    USER_TYPE_FINGERPRINT: "Fingerprint",
    USER_TYPE_ACCOUNT: "Account",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up per-user switch entities (only when admin identity is configured)."""
    from . import IseoRuntimeData  # noqa: PLC0415

    runtime_data: IseoRuntimeData = entry.runtime_data
    coordinator = runtime_data.coordinator

    if not (
        entry.data.get(CONF_ADMIN_UUID) and entry.data.get(CONF_ADMIN_PRIV_SCALAR)
    ):
        return

    ha_uuids: set[str] = {
        uid.lower()
        for key in (CONF_UUID, CONF_ADMIN_UUID)
        if (uid := entry.data.get(key))
    }
    known_uuids: set[str] = set()

    @callback
    def _on_coordinator_update() -> None:
        """Add a switch entity for any user not yet tracked."""
        new_entities = []
        for user in coordinator.users:
            uid = user.uuid_hex.lower()
            if uid in ha_uuids or uid in known_uuids:
                continue
            known_uuids.add(uid)
            new_entities.append(IseoUserSwitch(coordinator, entry, user))
        if new_entities:
            async_add_entities(new_entities)

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))
    _on_coordinator_update()


class IseoUserSwitch(CoordinatorEntity[IseoLogCoordinator], SwitchEntity):
    """Switch that enables or disables a single enrolled lock user."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:account-lock"

    def __init__(
        self,
        coordinator: IseoLogCoordinator,
        entry: ConfigEntry,
        user: UserEntry,
    ) -> None:
        """Initialize the user switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._uuid_hex = user.uuid_hex.lower()
        self._user_type = user.user_type
        self._optimistic_state: bool | None = None
        addr = entry.data[CONF_ADDRESS].replace(":", "").lower()
        self._attr_unique_id = f"{addr}_user_{self._uuid_hex}"
        type_label = _USER_TYPE_LABELS.get(user.user_type, f"type{user.user_type}")
        self._attr_name = user.name or f"{type_label} {self._uuid_hex[:8]}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    def _current_user(self) -> UserEntry | None:
        return next(
            (
                u
                for u in self.coordinator.users
                if u.uuid_hex.lower() == self._uuid_hex
            ),
            None,
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Clear optimistic state once the coordinator has confirmed the real state."""
        self._optimistic_state = None
        super()._handle_coordinator_update()

    @property
    def is_on(self) -> bool | None:
        """Return True when the user is enabled (can access the lock)."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        user = self._current_user()
        return None if user is None else not user.disabled

    @property
    def available(self) -> bool:
        """Return availability."""
        return (
            self.coordinator.last_update_success
            and self._current_user() is not None
        )

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable the user (remove time profile restriction)."""
        await self._set_disabled(False)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable the user (set an expired time profile)."""
        await self._set_disabled(True)

    async def _set_disabled(self, disabled: bool) -> None:
        admin_client = await self.hass.async_add_executor_job(
            self.coordinator.make_admin_client
        )
        if admin_client is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="admin_not_configured",
            )
        self._optimistic_state = not disabled
        self.async_write_ha_state()
        try:
            await admin_client.set_user_disabled(
                uuid_hex=self._uuid_hex,
                user_type=self._user_type,
                disabled=disabled,
            )
        except (IseoAuthError, IseoConnectionError) as exc:
            action = "disable" if disabled else "enable"
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="user_action_failed",
            ) from exc
        finally:
            self._optimistic_state = None
            self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
