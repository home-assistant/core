"""Support for Yale Access Bluetooth locks."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Coroutine, Generator
from contextlib import asynccontextmanager, contextmanager
from datetime import datetime
import logging
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

from homeassistant.components import bluetooth
from homeassistant.components.lock import LockEntity
from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID, ATTR_NAME
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later

from . import YALEXSBLEConfigEntry
from .const import (
    ACTIVITY_HOLD_SECONDS,
    ACTIVITY_SETTLE_SECONDS,
    ATTR_MASTER_CODE,
    ATTR_SLOT,
    ATTR_SOURCE,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    HA_OPERATION_TIMEOUT_SECONDS,
    YaleXSBLEServiceArgument,
    changed_by_for_source,
)
from .entity import YALEXSBLEEntity
from .models import ExpectedOperation, YaleXSBLEData

_LOGGER = logging.getLogger(__name__)

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
    """Return if a failed set left the slot as it was.

    That is when only the clear step failed, or the lock was not running so
    nothing was sent.
    """
    return isinstance(err, RuntimeError) or (
        isinstance(err, KeycodeError) and err.command == "clear_keycode"
    )


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
    except ValueError:
        # The library's message carries the raw PIN bytes of a malformed read.
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="invalid_response"
        ) from None
    except (YaleXSBLEError, BleakError, EOFError, OSError, TimeoutError) as err:
        # Library messages can include decrypted frames, which hold the PIN.
        _LOGGER.debug("Keycode operation failed: %s", type(err).__name__)
        raise HomeAssistantError(
            translation_domain=DOMAIN, translation_key="communication_error"
        ) from None
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
    _candidate: LockActivity | None = None
    _settle_cancel: CALLBACK_TYPE | None = None

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
            if (
                self._candidate is not None
                and MATCH_STATUS[new_state.lock]
                is not MATCH_STATUS[self._candidate.status]
            ):
                self._async_cancel_candidate()
            if self._hold_cancel is None:
                self._hold_cancel = async_call_later(
                    self.hass, ACTIVITY_HOLD_SECONDS, self._async_hold_expired
                )
            return
        self._async_cancel_hold()
        if new_state.lock is not self._lock_status:
            self._attr_changed_by = None
            if self._context is self._data.last_activity_context:
                # Keep a newer Home Assistant context but not a stale activity one.
                self._context = None
                self._context_set = None
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
        operations = self._data.expected_operations
        now = time.monotonic()
        operations[:] = [op for op in operations if now <= op.deadline]
        if any(op.matched_state is new_state for op in operations):
            return True
        operations[:] = [op for op in operations if op.matched_state is None]
        for index, operation in enumerate(operations):
            if new_state.lock in operation.statuses:
                operation.matched_state = new_state
                # Older commands were superseded by this outcome.
                del operations[:index]
                return True
        operations.clear()
        return False

    @asynccontextmanager
    async def _expect_operation(
        self, statuses: frozenset[LockStatus]
    ) -> AsyncGenerator[None]:
        """Expect a lock operation for the duration of the library call.

        Commands for one physical lock run one at a time, but a command can
        return before its state arrives, so expectations queue up in order.
        """
        data = self._data
        async with data.operation_lock:
            expected = ExpectedOperation(
                statuses, time.monotonic() + HA_OPERATION_TIMEOUT_SECONDS
            )
            data.expected_operations.append(expected)
            try:
                yield
            except BaseException:
                # Includes cancellation, which would otherwise leave the expectation active.
                data.expected_operations[:] = [
                    op for op in data.expected_operations if op is not expected
                ]
                raise

    @callback
    def _async_cancel_hold(self) -> None:
        """Cancel the hold timer and drop any pending state."""
        self._pending = None
        self._async_cancel_candidate()
        if self._hold_cancel is not None:
            self._hold_cancel()
            self._hold_cancel = None

    @callback
    def _async_cancel_candidate(self) -> None:
        """Drop the candidate activity and its settle timer."""
        self._candidate = None
        if self._settle_cancel is not None:
            self._settle_cancel()
            self._settle_cancel = None

    @callback
    def _async_arm_settle(self) -> None:
        """Wait for the activity backlog to stop arriving before attributing."""
        if self._settle_cancel is not None:
            self._settle_cancel()
        self._settle_cancel = async_call_later(
            self.hass, ACTIVITY_SETTLE_SECONDS, self._async_settled
        )

    @callback
    def _async_settled(self, _now: datetime) -> None:
        """Attribute the held state once no newer activity has arrived."""
        self._settle_cancel = None
        self._async_attribute_candidate()

    @callback
    def _async_attribute_candidate(self) -> None:
        """Write the held state with the candidate activity as its cause."""
        activity = self._candidate
        assert activity is not None
        self.async_set_context(self._activity_context_for(activity))
        self._attr_changed_by = self._changed_by_for(activity)
        self._async_flush_hold()

    @callback
    @override
    def _async_device_unavailable(
        self, service_info: bluetooth.BluetoothServiceInfoBleak
    ) -> None:
        """Drop any held state so its expiry cannot make the lock look available."""
        self._async_cancel_hold()
        super()._async_device_unavailable(service_info)

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
        if self._candidate is not None:
            self._async_attribute_candidate()
            return
        self._attr_changed_by = None
        self._context = None
        self._context_set = None
        self._async_flush_hold()

    @override
    async def async_added_to_hass(self) -> None:
        """Register the activity listener."""
        self.async_on_remove(
            self._data.async_add_activity_listener(self._async_activity)
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
                ATTR_ENTITY_ID: data.main_lock_entity_id or self.entity_id,
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
        if self._candidate is not None:
            self._async_arm_settle()
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
            self._candidate = activity
            self._async_arm_settle()
            return
        if activity_status != MATCH_STATUS.get(self._lock_status):
            return
        self._attr_changed_by = changed_by
        self.async_write_ha_state()

    @override
    async def async_unlock(self, **kwargs: Any) -> None:
        """Unlock the lock."""
        async with self._expect_operation(UNLOCK_STATUSES):
            await self._device.unlock()

    async def _async_run_once[T](
        self,
        name: str,
        data: dict[str, Any],
        operation: Callable[[], Coroutine[Any, Any, T]],
    ) -> T:
        """Run a credential operation once per service call across sibling entities."""
        assert self._context is not None
        # A context spans a script run, so parallel calls need the data to tell apart.
        key = (name, self._context.id, tuple(sorted(data.items())))
        # The action never changes state, so keep its context off later writes,
        # including those from lock actions that run while it is in progress.
        self._context = None
        self._context_set = None
        operations = self._data.credential_operations
        if (task := operations.get(key)) is None:
            task = self.hass.async_create_task(operation())
            operations[key] = task
            task.add_done_callback(lambda _: operations.pop(key, None))
        result: T = await task
        return result

    async def async_set_lock_credential(self, **kwargs: Any) -> None:
        """Set a keypad PIN."""
        await self._async_run_once(
            "set", kwargs, lambda: self._set_credential(**kwargs)
        )

    async def _set_credential(self, **kwargs: Any) -> None:
        """Set a keypad PIN on the lock."""
        pin: str = kwargs[YaleXSBLEServiceArgument.CREDENTIAL_DATA]
        if not PIN_PATTERN.fullmatch(pin):
            raise ServiceValidationError(
                translation_domain=DOMAIN, translation_key="invalid_pin"
            )
        slot: int = kwargs[YaleXSBLEServiceArgument.CREDENTIAL_INDEX]
        try:
            with _translate_keycode_errors():
                await self._device.set_keycode(slot, pin)
        except HomeAssistantError as err:
            if not _keycode_slot_unchanged(err.__cause__):
                await self._data.credential_names.async_remove(slot)
            raise
        except asyncio.CancelledError:
            # Programming may have started, so the old label might be wrong.
            await self._data.credential_names.async_remove(slot)
            raise
        if name := kwargs.get(YaleXSBLEServiceArgument.NAME):
            await self._data.credential_names.async_set(slot, name)

    async def async_clear_lock_credential(self, **kwargs: Any) -> None:
        """Clear a keypad PIN."""
        await self._async_run_once(
            "clear", kwargs, lambda: self._clear_credential(**kwargs)
        )

    async def _clear_credential(self, **kwargs: Any) -> None:
        """Clear a keypad PIN on the lock."""
        slot: int = kwargs[YaleXSBLEServiceArgument.CREDENTIAL_INDEX]
        with _translate_keycode_errors():
            await self._device.clear_keycode(slot)
        await self._data.credential_names.async_remove(slot)

    async def async_get_lock_credential_status(
        self, **kwargs: Any
    ) -> dict[str, bool | str | None]:
        """Return whether a keypad PIN slot is in use, never the PIN itself."""
        return await self._async_run_once(
            "status", kwargs, lambda: self._credential_status(**kwargs)
        )

    async def _credential_status(self, **kwargs: Any) -> dict[str, bool | str | None]:
        """Read a keypad PIN slot from the lock."""
        slot: int = kwargs[YaleXSBLEServiceArgument.CREDENTIAL_INDEX]
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
    async def async_added_to_hass(self) -> None:
        """Publish this entity as the owner of activity events."""
        self._data.main_lock_entity_id = self.entity_id
        await super().async_added_to_hass()

    @callback
    @override
    def async_entity_id_changed(self, old_entity_id: str) -> None:
        """Follow the entity_id in activity events."""
        super().async_entity_id_changed(old_entity_id)
        self._data.main_lock_entity_id = self.entity_id

    @override
    async def async_will_remove_from_hass(self) -> None:
        """Stop owning activity events."""
        self._data.main_lock_entity_id = None
        await super().async_will_remove_from_hass()

    @override
    async def async_lock(self, **kwargs: Any) -> None:
        """Lock the lock."""
        async with self._expect_operation(LOCK_STATUSES):
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
        async with self._expect_operation(SECURE_MODE_STATUSES):
            await self._device.securemode()
