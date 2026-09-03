"""ISEO Argo BLE lock credential sensors."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import replace
from typing import cast, override

from iseo_argo_ble import (
    USER_TYPE_ACCOUNT,
    USER_TYPE_BT,
    USER_TYPE_FINGERPRINT,
    USER_TYPE_INVITATION,
    USER_TYPE_PIN,
    USER_TYPE_RFID,
    IseoAuthError,
    IseoClient,
    IseoConnectionError,
    UserEntry,
)

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IseoConfigEntry
from .const import ADMIN_SETTLE_DELAY, CONF_ADMIN_UUID, DEFAULT_USER_SUBTYPE, DOMAIN
from .coordinator import IseoUserCoordinator

PARALLEL_UPDATES = 1

# The credential kind is part of the entity name: a person often holds several
# (a card and a phone), and the lock lets them share a name.
USER_TYPE_TRANSLATION_KEYS = {
    USER_TYPE_RFID: "credential_rfid",
    USER_TYPE_BT: "credential_phone",
    USER_TYPE_PIN: "credential_pin",
    USER_TYPE_INVITATION: "credential_invitation",
    USER_TYPE_FINGERPRINT: "credential_fingerprint",
    USER_TYPE_ACCOUNT: "credential_account",
}


def _is_home_assistant_identity(user: UserEntry, admin_uuid_hex: str | None) -> bool:
    """Return True for the two identities Home Assistant enrolled for itself."""
    if user.user_type == USER_TYPE_BT and user.inner_subtype == DEFAULT_USER_SUBTYPE:
        return True
    return bool(admin_uuid_hex) and user.uuid_hex == admin_uuid_hex


async def async_setup_entry(
    hass: HomeAssistant,
    entry: IseoConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up a sensor per lock credential from a config entry."""
    if (coordinator := entry.runtime_data.user_coordinator) is None:
        return

    admin_uuid_hex = entry.data.get(CONF_ADMIN_UUID)
    async_add_entities(
        IseoCredentialSensor(coordinator, user)
        for user in coordinator.data
        if not _is_home_assistant_identity(user, admin_uuid_hex)
    )


class IseoCredentialSensor(CoordinatorEntity[IseoUserCoordinator], BinarySensorEntity):
    """Reports whether one credential enrolled on the lock may open the door.

    Read-only on purpose. Suspending someone's credential is a change to who
    can get in, so it goes through the `set_credential_enabled` action, which
    only administrators may call.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: IseoUserCoordinator, user: UserEntry) -> None:
        """Initialize the credential sensor."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._uuid_hex = user.uuid_hex
        self._user_type = user.user_type
        self._inner_subtype = user.inner_subtype

        self._attr_translation_key = USER_TYPE_TRANSLATION_KEYS.get(
            user.user_type, "credential_other"
        )
        # Credentials enrolled without a name are only identifiable by UUID.
        self._attr_translation_placeholders = {
            "name": user.name.strip() or user.uuid_hex[:8]
        }
        self._attr_unique_id = (
            f"{entry.unique_id}_user_{user.user_type}_{user.uuid_hex}"
        )
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, cast(str, entry.unique_id))},
        )
        self._attr_is_on = not user.disabled

    @property
    def _user(self) -> UserEntry | None:
        """Return this sensor's credential in the current coordinator data."""
        return next(
            (
                user
                for user in self.coordinator.data
                if user.uuid_hex == self._uuid_hex and user.user_type == self._user_type
            ),
            None,
        )

    @property
    @override
    def available(self) -> bool:
        """Return True while the lock still lists this credential."""
        return super().available and self._user is not None

    @override
    def _handle_coordinator_update(self) -> None:
        """Take the new state, unless the credential is gone from the lock."""
        if (user := self._user) is not None:
            self._attr_is_on = not user.disabled
        super()._handle_coordinator_update()

    @override
    async def async_update(self) -> None:
        """Do nothing, on purpose.

        `CoordinatorEntity` would ask the coordinator to refresh, which re-reads
        the credential list over an admin session. Repeating that is what faults
        the lock's firmware, so `homeassistant.update_entity` is inert here.
        Reload the config entry to pick up credentials changed elsewhere.
        """

    @asynccontextmanager
    async def _admin_session(self) -> AsyncIterator[IseoClient]:
        """Hold the BLE mutex for one admin operation on this credential."""
        entry = self.coordinator.config_entry
        address = entry.data[CONF_ADDRESS]
        if not (
            ble_device := async_ble_device_from_address(
                self.hass, address, connectable=True
            )
        ):
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="device_not_found",
                translation_placeholders={"address": address},
            )

        try:
            async with entry.runtime_data.ble_lock:
                self.coordinator.client.update_ble_device(ble_device)
                yield self.coordinator.client
                # Targeting several credentials runs this once per entity, so
                # keep the mutex while the lock closes the admin session.
                await asyncio.sleep(ADMIN_SETTLE_DELAY)
        except IseoAuthError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="admin_rejected_identity",
            ) from err
        except (TimeoutError, IseoConnectionError, OSError) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="cannot_connect",
            ) from err

    async def async_set_enabled(self, enabled: bool) -> None:
        """Let this credential open the lock, or stop it doing so."""
        async with self._admin_session() as client:
            await client.set_user_disabled(
                uuid_hex=self._uuid_hex,
                user_type=self._user_type,
                disabled=not enabled,
            )

        self._apply_to_cached_users(disabled=not enabled)

    async def async_delete_credential(self) -> None:
        """Remove this credential from the lock for good.

        There is no undo from Home Assistant: whoever held it has to be
        enrolled again with the Master Card.
        """
        async with self._admin_session() as client:
            await client.erase_user_by_uuid(
                uuid_bytes=bytes.fromhex(self._uuid_hex),
                user_type=self._user_type,
                subtype=self._inner_subtype,
            )

        self.coordinator.async_set_updated_data(
            [
                user
                for user in self.coordinator.data
                if user.uuid_hex != self._uuid_hex or user.user_type != self._user_type
            ]
        )
        er.async_get(self.hass).async_remove(self.entity_id)

    def _apply_to_cached_users(self, *, disabled: bool) -> None:
        """Patch the cached credential list rather than re-reading it.

        Re-reading costs a second BLE session — connect, ECDH, admin login and a
        paginated read of every credential — to learn a value we just wrote, and
        the lock answers nobody else while it runs. The write above raises on
        failure, so getting here means the lock took it.
        """
        self.coordinator.async_set_updated_data(
            [
                replace(user, disabled=disabled)
                if user.uuid_hex == self._uuid_hex and user.user_type == self._user_type
                else user
                for user in self.coordinator.data
            ]
        )
