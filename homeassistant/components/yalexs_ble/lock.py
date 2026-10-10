"""Support for Yale Access Bluetooth locks."""

from collections.abc import Generator
from contextlib import contextmanager
from datetime import datetime
import re
import time
from typing import Any, override

from bleak.exc import BleakError
from yalexs_ble import (
    KEYPAD_MASTER_CODE_SLOT,
    ConnectionInfo,
    DoorActivity,
    KeycodeError,
    LockActivity,
    LockInfo,
    LockState,
    LockStatus,
    YaleXSBLEError,
)
from yalexs_ble.const import OperationError

from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import YALEXSBLEConfigEntry
from .const import (
    ACTIVITY_HOLD_SECONDS,
    ATTR_CREDENTIAL_DATA,
    ATTR_CREDENTIAL_INDEX,
    ATTR_MASTER_CODE,
    ATTR_SLOT,
    ATTR_SOURCE,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    HA_OPERATION_TIMEOUT_SECONDS,
    activity_signal,
    changed_by_for_source,
)
from .entity import YALEXSBLEEntity
from .models import ExpectedOperation, YaleXSBLEData

PIN_PATTERN = re.compile(r"[0-9]{4,8}")

HOLD_STATUSES = frozenset(
    {LockStatus.LOCKED, LockStatus.UNLOCKED, LockStatus.SECUREMODE}
)

MATCH_STATUS: dict[LockStatus, LockStatus] = {
    LockStatus.LOCKED: LockStatus.LOCKED,
    LockStatus.SECUREMODE: LockStatus.LOCKED,
    LockStatus.UNLOCKED: LockStatus.UNLOCKED,
}


LOCK_STATUSES = frozenset({LockStatus.LOCKED})
SECURE_MODE_STATUSES = frozenset({LockStatus.SECUREMODE, LockStatus.LOCKED})
UNLOCK_STATUSES = frozenset({LockStatus.UNLOCKED})


def _keycode_slot_unchanged(err: BaseException | None) -> bool:
    """Return if a failed set left the slot as it was, as only the clear step failed."""
    return isinstance(err, KeycodeError) and err.command == "clear_keycode"


@contextmanager
def _translate_keycode_errors() -> Generator[None]:
    """Translate library errors from keycode operations."""
    try:
        yield
    except KeycodeError as err:
        if err.error is OperationError.KEYCODE_EXISTING_KEY:
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="pin_already_in_use"
            ) from err
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="keycode_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except (YaleXSBLEError, BleakError, EOFError, OSError, TimeoutError) as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="communication_error",
            translation_placeholders={"error": str(err)},
        ) from err
    except RuntimeError as err:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="lock_not_running",
        ) from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: YALEXSBLEConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up locks."""
    async_add_entities(
        [YaleXSBLELock(entry.runtime_data), YaleXSBLESecureModeLock(entry.runtime_data)]
    )


class YaleXSBLEBaseLock(YALEXSBLEEntity, LockEntity):
    """A yale xs ble lock."""

    _secure_mode: bool = False
    _lock_status: LockStatus = LockStatus.UNKNOWN
    _pending: tuple[LockState, LockInfo, ConnectionInfo] | None = None
    _hold_cancel: CALLBACK_TYPE | None = None
    _activity_context: Context | None = None

    @callback
    @override
    def _async_update_state(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Update the state."""
        self._attr_is_locked = False
        self._attr_is_locking = False
        self._attr_is_unlocking = False
        self._attr_is_jammed = False
        lock_state = new_state.lock
        self._lock_status = lock_state
        if lock_state is LockStatus.LOCKED:
            self._attr_is_locked = not self._secure_mode
        elif lock_state is LockStatus.LOCKING:
            self._attr_is_locking = True
        elif lock_state is LockStatus.UNLOCKING:
            self._attr_is_unlocking = True
        elif lock_state is LockStatus.SECUREMODE:
            self._attr_is_locked = True
        elif lock_state in (
            LockStatus.UNKNOWN_01,
            LockStatus.UNKNOWN_06,
            LockStatus.JAMMED,
        ):
            self._attr_is_jammed = True
        elif lock_state is LockStatus.UNKNOWN:
            self._attr_is_locked = None
        super()._async_update_state(new_state, lock_info, connection_info)

    @callback
    @override
    def _async_state_changed(
        self, new_state: LockState, lock_info: LockInfo, connection_info: ConnectionInfo
    ) -> None:
        """Hold externally caused lock transitions until the cause is known."""
        if self._should_hold(new_state):
            self._pending = (new_state, lock_info, connection_info)
            if self._hold_cancel is None:
                self._hold_cancel = async_call_later(
                    self.hass, ACTIVITY_HOLD_SECONDS, self._async_hold_expired
                )
            return
        self._async_cancel_hold()
        if new_state.lock is not self._lock_status:
            self._attr_changed_by = None
        super()._async_state_changed(new_state, lock_info, connection_info)

    def _should_hold(self, new_state: LockState) -> bool:
        """Return if the state change should wait for its activity."""
        if new_state.lock not in HOLD_STATUSES:
            return False
        if self._pending is None and new_state.lock is self._lock_status:
            return False
        return not self._matches_expected_operation(new_state)

    def _matches_expected_operation(self, new_state: LockState) -> bool:
        """Return if the state is the outcome of a pending Home Assistant operation."""
        data = self._data
        if (operation := data.expected_operation) is None:
            return False
        if (
            operation.matched_state is not None
            and operation.matched_state is not new_state
        ) or time.monotonic() > operation.deadline:
            data.expected_operation = None
            return False
        if new_state.lock not in operation.statuses:
            data.expected_operation = None
            return False
        operation.matched_state = new_state
        return True

    @contextmanager
    def _expect_operation(self, statuses: frozenset[LockStatus]) -> Generator[None]:
        """Expect a lock operation for the duration of the library call."""
        data = self._data
        data.expected_operation = ExpectedOperation(
            statuses, time.monotonic() + HA_OPERATION_TIMEOUT_SECONDS
        )
        try:
            yield
        except Exception:
            data.expected_operation = None
            raise

    @callback
    def _async_cancel_hold(self) -> None:
        """Cancel the hold timer and drop any pending state."""
        self._pending = None
        if self._hold_cancel is not None:
            self._hold_cancel()
            self._hold_cancel = None

    @callback
    def _async_flush_hold(self) -> None:
        """Apply the pending state and write it."""
        pending = self._pending
        assert pending is not None
        self._async_cancel_hold()
        self._async_update_state(*pending)
        self.async_write_ha_state()

    @callback
    def _async_hold_expired(self, _now: datetime) -> None:
        """Write the held state without a known cause."""
        self._hold_cancel = None
        self._attr_changed_by = None
        if self._context is not None and self._context is self._activity_context:
            self._context = None
            self._context_set = None
        self._async_flush_hold()

    @override
    async def async_added_to_hass(self) -> None:
        """Register the activity listener."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, activity_signal(self._device.address), self._async_activity
            )
        )
        await super().async_added_to_hass()

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Cancel the hold timer."""
        self._async_cancel_hold()
        await super().async_will_remove_from_hass()

    def _changed_by_for(self, activity: LockActivity) -> str | None:
        """Return the changed_by text for an activity."""
        slot = activity.slot
        return changed_by_for_source(
            activity.source.name.lower(),
            slot,
            self._data.credential_names.get(slot) if slot is not None else None,
            self._data.master_code_name,
        )

    def _activity_context_for(self, activity: LockActivity) -> Context:
        """Fire the activity event once per activity and return its context."""
        data = self._data
        if data.last_activity is activity and data.last_activity_context is not None:
            return data.last_activity_context
        context = Context()
        data.last_activity = activity
        data.last_activity_context = context
        assert self.registry_entry is not None
        is_master_code = activity.slot == KEYPAD_MASTER_CODE_SLOT
        name: str | None = None
        if is_master_code:
            name = self._data.master_code_name
        elif activity.slot is not None:
            name = self._data.credential_names.get(activity.slot)
        self.hass.bus.async_fire(
            EVENT_LOCK_ACTIVITY,
            {
                ATTR_DEVICE_ID: self.registry_entry.device_id,
                ATTR_ENTITY_ID: self.entity_id,
                ATTR_SOURCE: activity.source.name.lower(),
                ATTR_SLOT: None if is_master_code else activity.slot,
                ATTR_MASTER_CODE: is_master_code,
                ATTR_NAME: name,
            },
            context=context,
        )
        return context

    @callback
    def _async_activity(self, activity: LockActivity | DoorActivity) -> None:
        """Attribute a lock activity to the held or current lock state."""
        if not isinstance(activity, LockActivity):
            return
        if (changed_by := self._changed_by_for(activity)) is None:
            return
        activity_status = MATCH_STATUS.get(activity.status)
        if activity_status is None:
            return
        if self._pending is not None:
            if activity_status is not MATCH_STATUS[self._pending[0].lock]:
                return
            context = self._activity_context_for(activity)
            self._activity_context = context
            self.async_set_context(context)
            self._attr_changed_by = changed_by
            self._async_flush_hold()
            return
        if activity_status != MATCH_STATUS.get(self._lock_status):
            return
        self._attr_changed_by = changed_by
        self.async_write_ha_state()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        with self._expect_operation(UNLOCK_STATUSES):
            await self._device.unlock()

    async def async_set_lock_credential(self, **kwargs: Any) -> None:
        """Set a keypad PIN."""
        pin: str = kwargs[ATTR_CREDENTIAL_DATA]
        if not PIN_PATTERN.fullmatch(pin):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_pin"
            )
        slot: int = kwargs[ATTR_CREDENTIAL_INDEX]
        try:
            with _translate_keycode_errors():
                await self._device.set_keycode(slot, pin)
        except HomeAssistantError as err:
            if not _keycode_slot_unchanged(err.__cause__):
                await self._data.credential_names.async_remove(slot)
            raise
        if name := kwargs.get(ATTR_NAME):
            await self._data.credential_names.async_set(slot, name)

    async def async_clear_lock_credential(self, **kwargs: Any) -> None:
        """Clear a keypad PIN."""
        slot: int = kwargs[ATTR_CREDENTIAL_INDEX]
        with _translate_keycode_errors():
            await self._device.clear_keycode(slot)
        await self._data.credential_names.async_remove(slot)

    async def async_get_lock_credential_status(
        self, **kwargs: Any
    ) -> dict[str, bool | str | None]:
        """Return whether a keypad PIN slot is in use, never the PIN itself."""
        slot: int = kwargs[ATTR_CREDENTIAL_INDEX]
        with _translate_keycode_errors():
            exists = await self._device.get_keycode(slot) is not None
        return {
            "credential_exists": exists,
            "name": self._data.credential_names.get(slot) if exists else None,
        }


class YaleXSBLELock(YaleXSBLEBaseLock, LockEntity):
    """A yale xs ble lock not in secure mode."""

    _attr_name = None

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        with self._expect_operation(LOCK_STATUSES):
            await self._device.lock()


class YaleXSBLESecureModeLock(YaleXSBLEBaseLock):
    """A yale xs ble lock in secure mode."""

    _attr_entity_registry_enabled_default = False
    _attr_translation_key = "secure_mode"
    _secure_mode = True

    def __init__(self, data: YaleXSBLEData) -> None:
        """Initialize the entity."""
        super().__init__(data)
        self._attr_unique_id = f"{self._device.address}_secure_mode"

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        with self._expect_operation(SECURE_MODE_STATUSES):
            await self._device.securemode()
