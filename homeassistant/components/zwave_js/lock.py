"""Representation of Z-Wave locks."""

from typing import Any

from zwave_js_server.const import CommandClass
from zwave_js_server.const.command_class.lock import (
    LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP,
    LOCK_CMD_CLASS_TO_PROPERTY_MAP,
    DoorLockCCConfigurationSetOptions,
    DoorLockMode,
    OperationType,
)
from zwave_js_server.exceptions import BaseZwaveJSServerError, NotFoundError
from zwave_js_server.util.lock import (
    clear_usercode,
    get_usercode,
    get_usercodes,
    set_configuration,
    set_usercode,
)

from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN, LockEntity, LockState
from homeassistant.core import HomeAssistant, ServiceResponse, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import const, lock_helpers
from .const import DOMAIN, LOGGER
from .discovery import ZwaveDiscoveryInfo
from .entity import ZWaveBaseEntity
from .lock_helpers import (
    CREDENTIAL_RULE_REVERSE_MAP,
    CREDENTIAL_TYPE_REVERSE_MAP,
    USER_TYPE_REVERSE_MAP,
    CredentialCapabilitiesResult,
    SetCredentialReturn,
    SetUserReturn,
    UsersResult,
)
from .models import ZwaveJSConfigEntry

PARALLEL_UPDATES = 0

STATE_TO_ZWAVE_MAP: dict[int, dict[str, int | bool]] = {
    CommandClass.DOOR_LOCK: {
        LockState.UNLOCKED: DoorLockMode.UNSECURED,
        LockState.LOCKED: DoorLockMode.SECURED,
    },
    CommandClass.LOCK: {
        LockState.UNLOCKED: False,
        LockState.LOCKED: True,
    },
}


def _credential_service_error(
    translation_key: str, err: Exception, **extra: str
) -> HomeAssistantError:
    """Wrap a zwave-js-server error with a credential-service translation."""
    return HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key=translation_key,
        translation_placeholders={"error": str(err), **extra},
    )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ZwaveJSConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Z-Wave lock from config entry."""
    client = config_entry.runtime_data.client

    @callback
    def async_add_lock(info: ZwaveDiscoveryInfo) -> None:
        """Add Z-Wave Lock."""
        driver = client.driver
        assert driver is not None  # Driver is ready before platforms are loaded.
        entities: list[ZWaveBaseEntity] = []
        entities.append(ZWaveLock(config_entry, driver, info))

        async_add_entities(entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(
            hass, f"{DOMAIN}_{config_entry.entry_id}_add_{LOCK_DOMAIN}", async_add_lock
        )
    )


class ZWaveLock(ZWaveBaseEntity, LockEntity):
    """Representation of a Z-Wave lock."""

    @property
    def is_locked(self) -> bool | None:
        """Return true if the lock is locked."""
        value = self.info.primary_value
        if value.value is None or (
            value.command_class == CommandClass.DOOR_LOCK
            and value.value == DoorLockMode.UNKNOWN
        ):
            # guard missing value
            return None
        return (
            LOCK_CMD_CLASS_TO_LOCKED_STATE_MAP[CommandClass(value.command_class)]
            == self.info.primary_value.value
        )

    async def _set_lock_state(self, target_state: LockState, **kwargs: Any) -> None:
        """Set the lock state."""
        target_value = self.get_zwave_value(
            LOCK_CMD_CLASS_TO_PROPERTY_MAP[
                CommandClass(self.info.primary_value.command_class)
            ]
        )
        if target_value is not None:
            await self._async_set_value(
                target_value,
                STATE_TO_ZWAVE_MAP[self.info.primary_value.command_class][target_state],
            )

    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        await self._set_lock_state(LockState.LOCKED)

    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        await self._set_lock_state(LockState.UNLOCKED)

    async def async_set_lock_usercode(self, code_slot: int, usercode: str) -> None:
        """Set the usercode to index X on the lock."""
        try:
            await set_usercode(self.info.node, code_slot, usercode)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="set_lock_usercode_failed",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "code_slot": str(code_slot),
                    "error": str(err),
                },
            ) from err
        LOGGER.debug("User code at slot %s on lock %s set", code_slot, self.entity_id)

    async def async_get_lock_usercode(
        self, code_slot: int | None = None
    ) -> ServiceResponse:
        """Get the usercode at index X on the lock."""
        if code_slot is not None:
            return self._get_single_usercode(code_slot)
        return self._get_all_usercodes()

    @callback
    def _get_single_usercode(self, code_slot: int) -> ServiceResponse:
        """Get the usercode at index X on the lock."""
        try:
            slot = get_usercode(self.info.node, code_slot)
        except NotFoundError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="get_lock_usercode_not_found",
                translation_placeholders={
                    "code_slot": str(code_slot),
                    "entity_id": self.entity_id,
                },
            ) from err
        return {
            str(code_slot): {
                "usercode": slot["usercode"],
                "in_use": slot["in_use"],
            },
        }

    @callback
    def _get_all_usercodes(self) -> ServiceResponse:
        """Get all usercodes from the lock."""
        slots = get_usercodes(self.info.node)
        return {
            str(slot["code_slot"]): {
                "usercode": slot["usercode"],
                "in_use": slot["in_use"],
            }
            for slot in slots
        }

    async def async_clear_lock_usercode(self, code_slot: int) -> None:
        """Clear the usercode at index X on the lock."""
        try:
            await clear_usercode(self.info.node, code_slot)
        except BaseZwaveJSServerError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="clear_lock_usercode_failed",
                translation_placeholders={
                    "entity_id": self.entity_id,
                    "code_slot": str(code_slot),
                    "error": str(err),
                },
            ) from err
        LOGGER.debug(
            "User code at slot %s on lock %s cleared", code_slot, self.entity_id
        )

    async def async_set_lock_configuration(
        self,
        operation_type: OperationType,
        lock_timeout: int | None = None,
        auto_relock_time: int | None = None,
        hold_and_release_time: int | None = None,
        twist_assist: bool | None = None,
        block_to_block: bool | None = None,
    ) -> None:
        """Set the lock configuration."""
        params: dict[str, Any] = {"operation_type": operation_type}
        params.update(
            {
                attr: val
                for attr, val in (
                    ("lock_timeout_configuration", lock_timeout),
                    ("auto_relock_time", auto_relock_time),
                    ("hold_and_release_time", hold_and_release_time),
                    ("twist_assist", twist_assist),
                    ("block_to_block", block_to_block),
                )
                if val is not None
            }
        )
        configuration = DoorLockCCConfigurationSetOptions(**params)
        result = await set_configuration(
            self.info.node.endpoints[self.info.primary_value.endpoint or 0],
            configuration,
        )
        if result is None:
            return
        msg = f"Result status is {result.status}"
        if result.remaining_duration is not None:
            msg += f" and remaining duration is {result.remaining_duration!s}"
        LOGGER.info("%s after setting lock configuration for %s", msg, self.entity_id)

    async def async_set_user(self, **kwargs: Any) -> SetUserReturn:
        """Create or update an access-control user on the lock."""
        user_type = kwargs.get(const.ATTR_USER_TYPE)
        credential_rule = kwargs.get(const.ATTR_CREDENTIAL_RULE)
        try:
            return await lock_helpers.async_set_user(
                self.info.node,
                user_id=kwargs.get(const.ATTR_USER_ID),
                user_name=kwargs.get(const.ATTR_USER_NAME),
                user_type=(
                    USER_TYPE_REVERSE_MAP[user_type] if user_type is not None else None
                ),
                credential_rule=(
                    CREDENTIAL_RULE_REVERSE_MAP[credential_rule]
                    if credential_rule is not None
                    else None
                ),
                active=kwargs.get(const.ATTR_USER_ACTIVE),
            )
        except BaseZwaveJSServerError as err:
            raise _credential_service_error("set_user_failed", err) from err

    async def async_delete_user(self, **kwargs: Any) -> None:
        """Delete a single access-control user."""
        user_id: int = kwargs[const.ATTR_USER_ID]
        try:
            await lock_helpers.async_delete_user(self.info.node, user_id)
        except BaseZwaveJSServerError as err:
            raise _credential_service_error(
                "delete_user_failed", err, user_id=str(user_id)
            ) from err

    async def async_delete_all_users(self) -> None:
        """Delete all access-control users."""
        try:
            await lock_helpers.async_delete_all_users(self.info.node)
        except BaseZwaveJSServerError as err:
            raise _credential_service_error("delete_all_users_failed", err) from err

    async def async_get_credential_capabilities(
        self,
    ) -> CredentialCapabilitiesResult:
        """Return credential management capabilities for the lock."""
        try:
            return await lock_helpers.async_get_credential_capabilities(self.info.node)
        except BaseZwaveJSServerError as err:
            raise _credential_service_error(
                "get_credential_capabilities_failed", err
            ) from err

    async def async_get_users(self) -> UsersResult:
        """Return access-control users for the lock."""
        try:
            return await lock_helpers.async_get_users(self.info.node)
        except BaseZwaveJSServerError as err:
            raise _credential_service_error("get_users_failed", err) from err

    async def async_set_credential(self, **kwargs: Any) -> SetCredentialReturn:
        """Add or update a credential for an existing user."""
        credential_type = kwargs[const.ATTR_CREDENTIAL_TYPE]
        try:
            return await lock_helpers.async_set_credential(
                self.info.node,
                user_id=kwargs[const.ATTR_USER_ID],
                credential_type=CREDENTIAL_TYPE_REVERSE_MAP[credential_type],
                credential_data=kwargs[const.ATTR_CREDENTIAL_DATA],
                credential_slot=kwargs.get(const.ATTR_CREDENTIAL_SLOT),
            )
        except BaseZwaveJSServerError as err:
            raise _credential_service_error("set_credential_failed", err) from err

    async def async_delete_credential(self, **kwargs: Any) -> None:
        """Delete a single credential."""
        try:
            await lock_helpers.async_delete_credential(
                self.info.node,
                user_id=kwargs[const.ATTR_USER_ID],
                credential_type=CREDENTIAL_TYPE_REVERSE_MAP[
                    kwargs[const.ATTR_CREDENTIAL_TYPE]
                ],
                credential_slot=kwargs[const.ATTR_CREDENTIAL_SLOT],
            )
        except BaseZwaveJSServerError as err:
            raise _credential_service_error("delete_credential_failed", err) from err

    async def async_delete_all_credentials(self, **kwargs: Any) -> None:
        """Delete all credentials for a user."""
        user_id: int = kwargs[const.ATTR_USER_ID]
        try:
            await lock_helpers.async_delete_all_credentials(self.info.node, user_id)
        except BaseZwaveJSServerError as err:
            raise _credential_service_error(
                "delete_all_credentials_failed", err, user_id=str(user_id)
            ) from err
