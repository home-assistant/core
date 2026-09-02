"""ISEO Argo BLE lock user switches."""

from dataclasses import replace
from typing import Any, cast, override

from iseo_argo_ble import (
    USER_TYPE_ACCOUNT,
    USER_TYPE_BT,
    USER_TYPE_FINGERPRINT,
    USER_TYPE_INVITATION,
    USER_TYPE_PIN,
    USER_TYPE_RFID,
    IseoAuthError,
    IseoConnectionError,
    UserEntry,
)

from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import CONF_ADDRESS, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import IseoConfigEntry
from .const import CONF_ADMIN_UUID, DEFAULT_USER_SUBTYPE, DOMAIN
from .coordinator import IseoUserCoordinator

PARALLEL_UPDATES = 1

# The credential kind is part of the entity name: a person often holds several
# (a card and a phone), and the lock lets them share a name.
USER_TYPE_TRANSLATION_KEYS = {
    USER_TYPE_RFID: "user_rfid",
    USER_TYPE_BT: "user_phone",
    USER_TYPE_PIN: "user_pin",
    USER_TYPE_INVITATION: "user_invitation",
    USER_TYPE_FINGERPRINT: "user_fingerprint",
    USER_TYPE_ACCOUNT: "user_account",
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
    """Set up a switch per lock user from a config entry."""
    if (coordinator := entry.runtime_data.user_coordinator) is None:
        return

    admin_uuid_hex = entry.data.get(CONF_ADMIN_UUID)
    async_add_entities(
        IseoUserSwitch(coordinator, user)
        for user in coordinator.data
        if not _is_home_assistant_identity(user, admin_uuid_hex)
    )


class IseoUserSwitch(CoordinatorEntity[IseoUserCoordinator], SwitchEntity):
    """Enables or disables one credential enrolled on the lock.

    Disabling a user leaves the credential on the lock but stops it opening the
    door, which is what the Argo app calls suspending a user.
    """

    _attr_has_entity_name = True
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: IseoUserCoordinator, user: UserEntry) -> None:
        """Initialize the user switch."""
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._uuid_hex = user.uuid_hex
        self._user_type = user.user_type

        self._attr_translation_key = USER_TYPE_TRANSLATION_KEYS.get(
            user.user_type, "user_other"
        )
        # Users enrolled without a name are only identifiable by their UUID.
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
        """Return this switch's user in the current coordinator data."""
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
        """Return True while the lock still lists this user."""
        return super().available and self._user is not None

    @override
    def _handle_coordinator_update(self) -> None:
        """Take the new state, unless the user is gone from the lock."""
        if (user := self._user) is not None:
            self._attr_is_on = not user.disabled
        super()._handle_coordinator_update()

    @override
    async def async_turn_on(self, **kwargs: Any) -> None:
        """Let the credential open the lock again."""
        await self._async_set_disabled(False)

    @override
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Stop the credential from opening the lock."""
        await self._async_set_disabled(True)

    async def _async_set_disabled(self, disabled: bool) -> None:
        """Write the new state to the lock."""
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
                await self.coordinator.client.set_user_disabled(
                    uuid_hex=self._uuid_hex,
                    user_type=self._user_type,
                    disabled=disabled,
                )
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

        self._apply_to_cached_users(disabled)

    def _apply_to_cached_users(self, disabled: bool) -> None:
        """Patch the cached user list rather than re-reading it.

        Re-reading costs a second BLE session — connect, ECDH, admin login and a
        paginated read of every user — to learn a value we just wrote, and the
        lock answers nobody else while it runs. The write above raises on
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
