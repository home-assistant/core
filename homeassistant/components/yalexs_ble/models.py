"""The yalexs_ble integration models."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from yalexs_ble import DoorActivity, LockActivity, LockState, LockStatus, PushLock

from homeassistant.core import CALLBACK_TYPE, Context, callback

from .store import CredentialNames


@dataclass
class ExpectedOperation:
    """A lock operation started from Home Assistant that is still in progress."""

    statuses: frozenset[LockStatus]
    deadline: float
    matched_state: LockState | None = None


@dataclass
class YaleXSBLEData:
    """Data for the yale xs ble integration."""

    title: str
    lock: PushLock
    always_connected: bool
    credential_names: CredentialNames
    master_code_name: str | None = None
    last_activity: LockActivity | None = None
    last_activity_context: Context | None = None
    main_lock_entity_id: str | None = None
    expected_operations: list[ExpectedOperation] = field(default_factory=list)
    operation_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    credential_operations: dict[
        tuple[str, str, tuple[tuple[str, Any], ...]], asyncio.Task[Any]
    ] = field(default_factory=dict)
    activity_listeners: set[Callable[[LockActivity | DoorActivity], None]] = field(
        default_factory=set
    )

    @callback
    def async_add_activity_listener(
        self, listener: Callable[[LockActivity | DoorActivity], None]
    ) -> CALLBACK_TYPE:
        """Add a lock activity listener and return a function to remove it."""
        self.activity_listeners.add(listener)
        return lambda: self.activity_listeners.discard(listener)
