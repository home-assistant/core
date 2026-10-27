"""Test the Yale Access Bluetooth lock credential services and changed_by."""

import asyncio
from collections.abc import AsyncGenerator, Callable, Generator
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakDBusError, BleakError
from bleak_retry_connector import BleakNotFoundError, BleakOutOfConnectionSlotsError
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
from pytest_homeassistant.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    async_fire_time_changed_exact,
)
from yalexs_ble import (
    KEYPAD_MASTER_CODE_SLOT,
    DoorActivity,
    KeycodeError,
    LockActivity,
    LockOperationSource,
    LockStatus,
    YaleXSBLEError,
)
from yalexs_ble.const import (
    AuthState,
    BatteryState,
    ConnectionInfo,
    DoorStatus,
    LockInfo,
    LockState,
    OperationError,
)
from yalexs_ble.session import ResponseError

from homeassistant.components.yalexs_ble.const import (
    ACTIVITY_HOLD_SECONDS,
    ACTIVITY_SETTLE_SECONDS,
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    HA_OPERATION_TIMEOUT_SECONDS,
)
from homeassistant.components.yalexs_ble.models import YaleXSBLEData
from homeassistant.components.yalexs_ble.store import CredentialNames
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, EVENT_STATE_CHANGED
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import YALE_ACCESS_LOCK_DISCOVERY_INFO

from tests.components.logbook.common import MockRow, mock_humanify

ENTITY_ID = "lock.front_door"
SECURE_ENTITY_ID = "lock.front_door_secure_mode"
STORAGE_KEY = "yalexs_ble.{}.credentials"


class MockLock:
    """Holder for the mocked PushLock and its captured callbacks."""

    def __init__(self) -> None:
        """Initialize the mock."""
        self.activity_callback: Callable[[Any], None] | None = None
        self.unregister_activity = MagicMock()
        self.push_lock = MagicMock()
        self.push_lock.address = YALE_ACCESS_LOCK_DISCOVERY_INFO.address
        self.push_lock.start = AsyncMock(return_value=MagicMock())
        self.push_lock.wait_for_first_update = AsyncMock()
        self.push_lock.get_keycode = AsyncMock(return_value=None)
        self.push_lock.set_keycode = AsyncMock()
        self.push_lock.clear_keycode = AsyncMock()
        self.push_lock.lock_state = LockState(
            lock=LockStatus.LOCKED,
            door=DoorStatus.CLOSED,
            battery=BatteryState(voltage=6.0, percentage=100),
            auth=AuthState(successful=True),
            auto_lock=None,
            auto_lock_prev=None,
        )
        self.push_lock.lock_info = LockInfo(
            manufacturer="Yale", model="YRD256", serial="1234", firmware="1.0"
        )
        self.push_lock.connection_info = ConnectionInfo(rssi=-60)
        self.push_lock.register_callback.side_effect = self._register_state
        self.push_lock.register_activity_callback.side_effect = self._register
        self.push_lock.unlock = AsyncMock()
        self.push_lock.lock = AsyncMock()
        self.calls: list[str] = []
        self.push_lock.start.side_effect = self._start
        self.state_callbacks: list[Callable[..., None]] = []

    async def _start(self) -> MagicMock:
        """Record the start call."""
        self.calls.append("start")
        return MagicMock()

    def _register_state(self, callback: Callable[..., None]) -> MagicMock:
        """Capture the state callbacks."""
        self.state_callbacks.append(callback)
        return MagicMock()

    def push(self, status: LockStatus, percentage: int = 100) -> None:
        """Push a new lock status to the entities."""
        state = replace(
            self.push_lock.lock_state,
            lock=status,
            battery=BatteryState(voltage=6.0, percentage=percentage),
        )
        for callback in self.state_callbacks:
            callback(state, self.push_lock.lock_info, self.push_lock.connection_info)

    def _register(self, callback: Callable[[Any], None]) -> MagicMock:
        """Capture the activity callback."""
        self.calls.append("register")
        self.activity_callback = callback
        return self.unregister_activity

    def fire(self, activity: LockActivity | DoorActivity) -> None:
        """Deliver an activity to the entity."""
        assert self.activity_callback is not None
        self.activity_callback(activity)


@pytest.fixture
def lock_address() -> str:
    """Return the address the mocked PushLock reports at runtime."""
    return YALE_ACCESS_LOCK_DISCOVERY_INFO.address


@pytest.fixture
def mock_lock(lock_address: str) -> MockLock:
    """Return a mocked lock."""
    lock = MockLock()
    lock.push_lock.address = lock_address
    return lock


@pytest.fixture
async def entry(
    hass: HomeAssistant, mock_lock: MockLock
) -> AsyncGenerator[MockConfigEntry]:
    """Set up a config entry with a mocked lock."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Front Door",
        data={
            CONF_LOCAL_NAME: YALE_ACCESS_LOCK_DISCOVERY_INFO.name,
            CONF_ADDRESS: YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
            CONF_KEY: "2fd51b8621c6a139eaffbedcb846b60f",
            CONF_SLOT: 66,
        },
        unique_id=YALE_ACCESS_LOCK_DISCOVERY_INFO.address,
    )
    config_entry.add_to_hass(hass)
    with (
        patch("homeassistant.components.yalexs_ble.close_stale_connections_by_address"),
        patch(
            "homeassistant.components.yalexs_ble.PushLock",
            return_value=mock_lock.push_lock,
        ),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        yield config_entry


def _call(
    hass: HomeAssistant, service: str, data: dict[str, Any], **kwargs: Any
) -> Any:
    """Call a yalexs_ble lock service."""
    return hass.services.async_call(
        DOMAIN,
        service,
        {"entity_id": ENTITY_ID, "credential_type": "pin", **data},
        blocking=True,
        **kwargs,
    )


@pytest.mark.usefixtures("entry")
async def test_set_credential_stores_name(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test setting a PIN with a name stores it and survives a reload."""
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "1234", "credential_index": 205, "name": "Jesse"},
    )

    mock_lock.push_lock.set_keycode.assert_awaited_once_with(205, "1234")
    assert hass_storage[STORAGE_KEY.format(entry.entry_id)]["data"] == {
        "names": {"205": "Jesse"}
    }

    with patch(
        "homeassistant.components.yalexs_ble.close_stale_connections_by_address"
    ):
        await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED

    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 205))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Jesse"


@pytest.mark.usefixtures("entry")
async def test_set_credential_without_name_keeps_existing(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test setting a PIN without a name keeps the existing label."""
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "1234", "credential_index": 5, "name": "Guest"},
    )
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "5678", "credential_index": 5},
    )

    assert hass_storage[STORAGE_KEY.format(entry.entry_id)]["data"] == {
        "names": {"5": "Guest"}
    }


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    "pin",
    ["123", "123456789", "12a4", "١٢٣٤"],
    ids=["short", "long", "alpha", "unicode"],
)
async def test_set_credential_invalid_pin(
    hass: HomeAssistant, mock_lock: MockLock, pin: str
) -> None:
    """Test an invalid PIN is rejected before talking to the lock."""
    with pytest.raises(ServiceValidationError, match="4 to 8 digits"):
        await _call(
            hass,
            "set_lock_credential",
            {"credential_data": pin, "credential_index": 1},
        )
    mock_lock.push_lock.set_keycode.assert_not_awaited()


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"credential_index": 0}, id="slot_low"),
        pytest.param({"credential_index": 251}, id="slot_high"),
        pytest.param({"credential_index": 1, "credential_type": "rfid"}, id="type"),
    ],
)
async def test_set_credential_schema_rejects(
    hass: HomeAssistant, mock_lock: MockLock, data: dict[str, Any]
) -> None:
    """Test the service schema rejects out of range slots and other types."""
    with pytest.raises(probatio.MultipleInvalid):
        await _call(hass, "set_lock_credential", {"credential_data": "1234", **data})
    mock_lock.push_lock.set_keycode.assert_not_awaited()


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("error", "exception", "message"),
    [
        pytest.param(
            KeycodeError("set", OperationError.KEYCODE_EXISTING_KEY),
            ServiceValidationError,
            "already used in another slot",
            id="existing_key",
        ),
        pytest.param(
            KeycodeError("set", OperationError.KEYCODE_NOSPACE),
            HomeAssistantError,
            "rejected the keypad request",
            id="keycode_error",
        ),
        pytest.param(
            YaleXSBLEError("boom"),
            HomeAssistantError,
            "Failed to communicate",
            id="ble_error",
        ),
        pytest.param(
            TimeoutError("slow"),
            HomeAssistantError,
            "Failed to communicate",
            id="timeout",
        ),
    ],
)
async def test_set_credential_errors(
    hass: HomeAssistant,
    mock_lock: MockLock,
    hass_storage: dict[str, Any],
    error: Exception,
    exception: type[Exception],
    message: str,
) -> None:
    """Test library errors are translated and no name is stored."""
    mock_lock.push_lock.set_keycode.side_effect = error
    with pytest.raises(exception, match=message):
        await _call(
            hass,
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 3, "name": "Nope"},
        )
    assert not any(key.startswith("yalexs_ble.") for key in hass_storage)


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("error", "expected_name"),
    [
        pytest.param(
            KeycodeError("clear_keycode", OperationError.KEYCODE_NOSPACE),
            "Guest",
            id="clear_failed",
        ),
        pytest.param(
            KeycodeError("commit_keycode", OperationError.KEYCODE_NOSPACE),
            None,
            id="commit_failed",
        ),
        pytest.param(RuntimeError("not running"), "Guest", id="not_running"),
        pytest.param(BleakError("gone"), None, id="bleak"),
    ],
)
async def test_failed_set_credential_name_handling(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    error: Exception,
    expected_name: str | None,
) -> None:
    """Test a failed set keeps the name only when the slot is unchanged."""
    entry.runtime_data.credential_names._names["3"] = "Guest"
    mock_lock.push_lock.set_keycode.side_effect = error
    with pytest.raises(HomeAssistantError):
        await _call(
            hass,
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 3},
        )
    assert entry.runtime_data.credential_names.get(3) == expected_name


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("method", "service", "data", "extra"),
    [
        pytest.param(
            "set_keycode",
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 3},
            {},
            id="set",
        ),
        pytest.param(
            "clear_keycode",
            "clear_lock_credential",
            {"credential_index": 3},
            {},
            id="clear",
        ),
        pytest.param(
            "get_keycode",
            "get_lock_credential_status",
            {"credential_index": 3},
            {"return_response": True},
            id="status",
        ),
    ],
)
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(BleakError("gone"), "communication_error", id="bleak"),
        pytest.param(
            BleakDBusError("org.bluez.Error", []),
            "communication_error",
            id="bleak_dbus",
        ),
        pytest.param(
            BleakOutOfConnectionSlotsError("no slots"),
            "communication_error",
            id="no_slots",
        ),
        pytest.param(
            BleakNotFoundError("missing"), "communication_error", id="not_found"
        ),
        pytest.param(EOFError("eof"), "communication_error", id="eof"),
        pytest.param(BrokenPipeError("pipe"), "communication_error", id="broken_pipe"),
        pytest.param(RuntimeError("not running"), "lock_not_running", id="not_running"),
        pytest.param(
            ValueError("Malformed PIN field: 1234ffffff"),
            "invalid_response",
            id="malformed_pin",
        ),
        pytest.param(
            ResponseError("bad frame 1234ffffff"),
            "communication_error",
            id="response_error",
        ),
    ],
)
async def test_credential_services_translate_library_errors(
    hass: HomeAssistant,
    mock_lock: MockLock,
    method: str,
    service: str,
    data: dict[str, Any],
    extra: dict[str, Any],
    error: Exception,
    translation_key: str,
) -> None:
    """Test every escaping library error is translated by each service."""
    getattr(mock_lock.push_lock, method).side_effect = error
    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(hass, service, data, **extra)
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders in (None, {})
    assert "1234" not in str(exc_info.value)


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("error", "translation_key"),
    [
        pytest.param(
            ValueError("Malformed PIN field: 1234ffffff"),
            "invalid_response",
            id="malformed_pin",
        ),
        pytest.param(
            ResponseError("frame 1234ffffff"), "communication_error", id="response"
        ),
    ],
)
async def test_credential_errors_do_not_expose_pin_data(
    hass: HomeAssistant,
    mock_lock: MockLock,
    error: Exception,
    translation_key: str,
) -> None:
    """Test PIN bytes in library errors never reach the raised error."""
    mock_lock.push_lock.get_keycode.side_effect = error
    with pytest.raises(HomeAssistantError) as exc_info:
        await _call(
            hass,
            "get_lock_credential_status",
            {"credential_index": 3},
            return_response=True,
        )
    assert exc_info.value.translation_key == translation_key
    assert exc_info.value.translation_placeholders is None
    assert exc_info.value.__cause__ is None
    assert "1234" not in str(exc_info.value)


@pytest.mark.usefixtures("entry")
async def test_clear_credential_removes_name(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test clearing a slot removes its stored name."""
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "1234", "credential_index": 7, "name": "Cleaner"},
    )
    await _call(hass, "clear_lock_credential", {"credential_index": 7})

    mock_lock.push_lock.clear_keycode.assert_awaited_once_with(7)
    assert hass_storage[STORAGE_KEY.format(entry.entry_id)]["data"] == {"names": {}}


@pytest.mark.usefixtures("entry")
async def test_clear_credential_unnamed_slot(
    hass: HomeAssistant, mock_lock: MockLock, hass_storage: dict[str, Any]
) -> None:
    """Test clearing a slot without a stored name does not write storage."""
    await _call(hass, "clear_lock_credential", {"credential_index": 8})

    mock_lock.push_lock.clear_keycode.assert_awaited_once_with(8)
    assert not any(key.startswith("yalexs_ble.") for key in hass_storage)


@pytest.mark.usefixtures("entry")
async def test_clear_credential_error(hass: HomeAssistant, mock_lock: MockLock) -> None:
    """Test clear errors are translated."""
    mock_lock.push_lock.clear_keycode.side_effect = YaleXSBLEError("boom")
    with pytest.raises(HomeAssistantError, match="Failed to communicate"):
        await _call(hass, "clear_lock_credential", {"credential_index": 8})


@pytest.mark.usefixtures("entry")
async def test_credential_status(hass: HomeAssistant, mock_lock: MockLock) -> None:
    """Test status reports existence and name but never the PIN."""
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "4321", "credential_index": 9, "name": "Nan"},
    )
    mock_lock.push_lock.get_keycode.return_value = "4321"

    response = await _call(
        hass,
        "get_lock_credential_status",
        {"credential_index": 9},
        return_response=True,
    )
    assert response == {
        ENTITY_ID: {"credential_exists": True, "name": "Nan"},
    }
    assert "4321" not in str(response)

    mock_lock.push_lock.get_keycode.return_value = None
    response = await _call(
        hass,
        "get_lock_credential_status",
        {"credential_index": 9},
        return_response=True,
    )
    assert response == {ENTITY_ID: {"credential_exists": False, "name": None}}


@pytest.mark.usefixtures("entry")
async def test_credential_status_error(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test status errors are translated."""
    mock_lock.push_lock.get_keycode.side_effect = KeycodeError(
        "get", OperationError.KEYCODE_TIMEOUT
    )
    with pytest.raises(HomeAssistantError, match="rejected the keypad request"):
        await _call(
            hass,
            "get_lock_credential_status",
            {"credential_index": 9},
            return_response=True,
        )


@pytest.mark.usefixtures("entry")
async def test_services_require_admin(
    hass: HomeAssistant, hass_read_only_user: MockUser
) -> None:
    """Test the credential services need an admin user."""
    with pytest.raises(Unauthorized):
        await _call(
            hass,
            "clear_lock_credential",
            {"credential_index": 1},
            context=Context(user_id=hass_read_only_user.id),
        )


def _activity(
    status: LockStatus, source: LockOperationSource, slot: int | None = None
) -> LockActivity:
    """Build a lock activity."""
    return LockActivity(dt_util.utcnow(), status, source, slot=slot)


async def _expire_hold(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time past the activity hold."""
    freezer.tick(timedelta(seconds=ACTIVITY_HOLD_SECONDS + 0.1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def _settle(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Advance time past the activity settle period."""
    freezer.tick(timedelta(seconds=ACTIVITY_SETTLE_SECONDS + 0.1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


def _writes(events: list[Any], entity_id: str = ENTITY_ID) -> list[Any]:
    """Return the state change events for an entity."""
    return [event for event in events if event.data["entity_id"] == entity_id]


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("source", "slot", "expected", "event_name"),
    [
        pytest.param(LockOperationSource.PIN, 12, "Keypad slot 12", None, id="pin"),
        pytest.param(LockOperationSource.PIN, 7, "Test", "Test", id="pin_named"),
        pytest.param(LockOperationSource.PIN, None, "Keypad", None, id="pin_no_slot"),
        pytest.param(LockOperationSource.MANUAL, None, "Manual", None, id="manual"),
        pytest.param(LockOperationSource.REMOTE, None, "Remote", None, id="remote"),
    ],
)
async def test_hold_then_activity(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    source: LockOperationSource,
    slot: int | None,
    expected: str,
    event_name: str | None,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a held transition is written once with the activity as its cause."""
    entry.runtime_data.credential_names._names["7"] = "Test"
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert not _writes(state_events)
    assert not activity_events

    mock_lock.fire(_activity(LockStatus.UNLOCKED, source, slot))
    await _settle(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == expected
    assert len(_writes(state_events)) == 1
    assert len(activity_events) == 1
    event = activity_events[0]
    device = device_registry.async_get_device_by_connection(
        ("bluetooth", YALE_ACCESS_LOCK_DISCOVERY_INFO.address), entry.entry_id
    )
    assert event.data == {
        "device_id": device.id,
        "entity_id": ENTITY_ID,
        "source": source.name.lower(),
        "slot": slot,
        "master_code": False,
        "name": event_name,
    }
    assert state.context.id == event.context.id


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("master_code_name", "expected"),
    [
        pytest.param(None, "Master code", id="unnamed"),
        pytest.param("Admin", "Admin", id="named"),
    ],
)
async def test_hold_master_code(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    master_code_name: str | None,
    expected: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a master code unlock is attributed with a flag instead of a slot."""
    entry.runtime_data.master_code_name = master_code_name
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(
        _activity(LockStatus.UNLOCKED, LockOperationSource.PIN, KEYPAD_MASTER_CODE_SLOT)
    )
    await _settle(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == expected
    (event,) = activity_events
    assert event.data["slot"] is None
    assert event.data["master_code"] is True
    assert event.data["name"] == master_code_name


@pytest.mark.parametrize(
    ("options", "expected"),
    [
        pytest.param({}, None, id="unset"),
        pytest.param({"master_code_name": ""}, None, id="empty"),
        pytest.param({"master_code_name": "Admin"}, "Admin", id="named"),
    ],
)
async def test_master_code_name_option(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    options: dict[str, str],
    expected: str | None,
) -> None:
    """Test the master code name option is applied when the entry reloads."""
    hass.config_entries.async_update_entry(entry, options=options)
    assert await hass.config_entries.async_reload(entry.entry_id)
    assert entry.runtime_data.master_code_name == expected


@pytest.mark.usefixtures("entry")
async def test_hold_auto_lock(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test an auto lock locking transition is attributed."""
    mock_lock.push(LockStatus.UNLOCKED)
    await _expire_hold(hass, freezer)
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.LOCKED)
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.AUTO_LOCK))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.attributes["changed_by"] == "Auto lock"
    assert activity_events[0].data["source"] == "auto_lock"


@pytest.mark.usefixtures("entry")
async def test_hold_timeout(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the state is written without a cause when no activity arrives."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert not _writes(state_events)

    await _expire_hold(hass, freezer)

    assert hass.states.get(ENTITY_ID).state == "unlocked"
    assert len(_writes(state_events)) == 1
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_hold_timeout_drops_previous_activity_context(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test an unattributed change does not reuse the previous cause."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    cause_id = hass.states.get(ENTITY_ID).context.id

    mock_lock.push(LockStatus.LOCKED)
    await _expire_hold(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.context.id != cause_id
    assert "changed_by" not in state.attributes


@pytest.mark.usefixtures("entry")
async def test_second_activity_not_treated_as_ha_initiated(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a change right after an attributed one is still held."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)

    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert len(activity_events) == 1


@pytest.mark.usefixtures("entry")
async def test_ha_initiated_change_not_held(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test a state change after a service call is written immediately."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_slow_ha_unlock_not_held(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test an HA operation whose status arrives late is still not held."""
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    freezer.tick(timedelta(seconds=10))
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_back_to_back_ha_operations_with_late_callbacks_not_held(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test commands returning before their callbacks keep every outcome HA initiated."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.services.async_call(
        "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True
    )
    assert (
        len(
            hass.config_entries.async_entries(DOMAIN)[
                0
            ].runtime_data.expected_operations
        )
        == 2
    )

    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    assert hass.states.get(SECURE_ENTITY_ID).state == "unlocked"

    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert hass.states.get(SECURE_ENTITY_ID).state == "unlocked"
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_external_change_clears_all_pending_operations(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test a non-matching transition drops every pending expectation."""
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    await hass.services.async_call(
        "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.SECUREMODE)
    await hass.async_block_till_done()
    assert not hass.config_entries.async_entries(DOMAIN)[
        0
    ].runtime_data.expected_operations
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"


@pytest.mark.usefixtures("entry")
async def test_expected_operation_expires(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a later external change is held once the HA operation timed out."""
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    freezer.tick(timedelta(seconds=HA_OPERATION_TIMEOUT_SECONDS + 1))
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entry")
async def test_external_change_after_ha_operation_held(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a completed HA operation does not make the next change HA initiated."""
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entry")
async def test_opposite_change_during_ha_operation_held(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a change that does not match the HA operation is held."""
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.SECUREMODE)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert (
        hass.states.get(ENTITY_ID).last_changed
        == hass.states.get(ENTITY_ID).last_updated
    )
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Manual"


@pytest.mark.usefixtures("entry")
async def test_concurrent_ha_operations_run_sequentially(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test overlapping HA commands run one at a time and both are HA initiated."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    release_unlock = asyncio.Event()
    order: list[str] = []

    async def _unlock() -> None:
        order.append("unlock start")
        await release_unlock.wait()
        order.append("unlock end")

    async def _lock() -> None:
        order.append("lock start")

    mock_lock.push_lock.unlock.side_effect = _unlock
    mock_lock.push_lock.lock.side_effect = _lock

    unlock_task = hass.async_create_task(
        hass.services.async_call(
            "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
        )
    )
    await asyncio.sleep(0)
    lock_task = hass.async_create_task(
        hass.services.async_call(
            "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True
        )
    )
    await asyncio.sleep(0)
    assert order == ["unlock start"]

    mock_lock.push(LockStatus.UNLOCKED)
    release_unlock.set()
    await asyncio.gather(unlock_task, lock_task)
    assert order == ["unlock start", "unlock end", "lock start"]
    assert hass.states.get(ENTITY_ID).state == "unlocked"

    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_failed_ha_operation_keeps_next_expectation(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test a failing command does not clear the next command's expectation."""
    release_unlock = asyncio.Event()
    seen: list[bool] = []

    async def _unlock() -> None:
        await release_unlock.wait()
        raise BleakError("gone")

    async def _lock() -> None:
        seen.append(bool(mock_lock_data().expected_operations))

    def mock_lock_data() -> YaleXSBLEData:
        return hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    mock_lock.push_lock.unlock.side_effect = _unlock
    mock_lock.push_lock.lock.side_effect = _lock

    unlock_task = hass.async_create_task(
        hass.services.async_call(
            "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
        )
    )
    await asyncio.sleep(0)
    lock_task = hass.async_create_task(
        hass.services.async_call(
            "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True
        )
    )
    await asyncio.sleep(0)
    release_unlock.set()
    results = await asyncio.gather(unlock_task, lock_task, return_exceptions=True)
    assert isinstance(results[0], BleakError)
    assert results[1] is None
    assert seen == [True]
    assert len(mock_lock_data().expected_operations) == 1


@pytest.mark.usefixtures("entry")
async def test_failed_ha_operation_after_expectation_consumed(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test a failure after the expectation was already dropped is a no-op."""

    async def _unlock() -> None:
        mock_lock.push(LockStatus.SECUREMODE)
        raise BleakError("gone")

    mock_lock.push_lock.unlock.side_effect = _unlock
    with pytest.raises(BleakError):
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
        )
    data = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    assert not data.expected_operations


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_noop_ha_operation_does_not_misattribute_later_change(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an HA command that changes nothing does not claim a later change."""
    mock_lock.push_lock.securemode = AsyncMock()
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "locked"

    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 4))
    await _settle(hass, freezer)
    assert len(activity_events) == 1
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 4"
    assert hass.states.get(SECURE_ENTITY_ID).state == "unlocked"


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("service", "start", "end"),
    [
        pytest.param("lock", LockStatus.UNLOCKED, LockStatus.LOCKED, id="lock"),
        pytest.param("unlock", LockStatus.LOCKED, LockStatus.UNLOCKED, id="unlock"),
    ],
)
async def test_failed_ha_operation_clears_expectation(
    hass: HomeAssistant,
    mock_lock: MockLock,
    service: str,
    start: LockStatus,
    end: LockStatus,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a failing library call does not leave an expected operation behind."""
    mock_lock.push(start)
    mock_lock.fire(_activity(start, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    getattr(mock_lock.push_lock, service).side_effect = BleakError("gone")
    with pytest.raises(BleakError):
        await hass.services.async_call(
            "lock", service, {"entity_id": ENTITY_ID}, blocking=True
        )
    mock_lock.push(end)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == start.name.lower()


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 3},
            id="set",
        ),
        pytest.param("clear_lock_credential", {"credential_index": 3}, id="clear"),
        pytest.param(
            "get_lock_credential_status", {"credential_index": 3}, id="status"
        ),
    ],
)
async def test_credential_action_does_not_suppress_attribution(
    hass: HomeAssistant,
    mock_lock: MockLock,
    service: str,
    data: dict[str, Any],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a credential action shortly before a keypad unlock still attributes it."""
    await _call(
        hass,
        service,
        data,
        return_response=service == "get_lock_credential_status",
    )
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"
    assert len(activity_events) == 1


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    "lock_address", [pytest.param("11:22:33:44:55:66", id="runtime_address_differs")]
)
async def test_activity_reaches_entity_with_different_runtime_address(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test attribution does not depend on the runtime address matching the entry."""
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entry")
async def test_changed_by_cleared_on_ha_initiated_change(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an HA initiated change drops the previous keypad attribution."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"

    await hass.services.async_call(
        "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert "changed_by" not in state.attributes

    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.REMOTE))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Remote"


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("status", "state"),
    [
        pytest.param(LockStatus.LOCKING, "locking", id="locking"),
        pytest.param(LockStatus.UNLOCKING, "unlocking", id="unlocking"),
        pytest.param(LockStatus.JAMMED, "jammed", id="jammed"),
    ],
)
async def test_changed_by_cleared_on_transitional_state(
    hass: HomeAssistant,
    mock_lock: MockLock,
    status: LockStatus,
    state: str,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test transitional and fault states drop the previous attribution."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"
    assert hass.states.get(ENTITY_ID).context.id == activity_events[0].context.id

    mock_lock.push(status)
    await hass.async_block_till_done()
    result = hass.states.get(ENTITY_ID)
    assert result.state == state
    assert "changed_by" not in result.attributes
    assert result.context.id != activity_events[0].context.id


@pytest.mark.usefixtures("entry")
async def test_changed_by_kept_on_battery_update(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an update that keeps the lock status keeps the attribution."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)

    mock_lock.push(LockStatus.UNLOCKED, percentage=50)
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
@pytest.mark.parametrize(
    ("entity_id", "status", "secure_state"),
    [
        pytest.param(ENTITY_ID, LockStatus.LOCKED, "unlocked", id="lock"),
        pytest.param(
            SECURE_ENTITY_ID, LockStatus.SECUREMODE, "locked", id="secure_mode"
        ),
        pytest.param(
            SECURE_ENTITY_ID, LockStatus.LOCKED, "unlocked", id="secure_mode_locked"
        ),
    ],
)
async def test_ha_operation_not_misattributed_with_both_entities(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entity_id: str,
    status: LockStatus,
    secure_state: str,
) -> None:
    """Test an HA operation on one lock entity is not held by its sibling."""
    mock_lock.push_lock.securemode = AsyncMock()
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await hass.async_block_till_done()
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)

    await hass.services.async_call(
        "lock", "lock", {"entity_id": entity_id}, blocking=True
    )
    mock_lock.push(status)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert hass.states.get(SECURE_ENTITY_ID).state == secure_state
    assert not activity_events


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_external_operation_one_event_with_both_entities(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an external change after an HA operation yields exactly one event."""
    mock_lock.push_lock.securemode = AsyncMock()
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)

    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    assert len(activity_events) == 1
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"
    assert (
        hass.states.get(SECURE_ENTITY_ID).context.id
        == hass.states.get(ENTITY_ID).context.id
    )


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("status", "state"),
    [
        pytest.param(LockStatus.LOCKING, "locking", id="locking"),
        pytest.param(LockStatus.UNLOCKING, "unlocking", id="unlocking"),
        pytest.param(LockStatus.JAMMED, "jammed", id="jammed"),
        pytest.param(LockStatus.UNKNOWN, "unknown", id="unknown"),
    ],
)
async def test_transitional_states_not_held(
    hass: HomeAssistant, mock_lock: MockLock, status: LockStatus, state: str
) -> None:
    """Test transitional and fault states are written immediately."""
    mock_lock.push(status)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == state


@pytest.mark.usefixtures("entry")
async def test_unchanged_status_not_held(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test updates that keep the lock status are written immediately."""
    mock_lock.push(LockStatus.LOCKED, percentage=50)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert (
        hass.states.get(ENTITY_ID).last_changed
        == hass.states.get(ENTITY_ID).last_updated
    )


@pytest.mark.usefixtures("entry")
async def test_transitional_state_ends_hold(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a transitional state during a hold is written and cancels it."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.push(LockStatus.LOCKING)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locking"
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    await _expire_hold(hass, freezer)
    assert not _writes(state_events)
    assert hass.states.get(ENTITY_ID).state == "locking"


@pytest.mark.usefixtures("entry")
async def test_state_updates_during_hold_replace_pending(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test later callbacks update the held state and secure mode matches locked."""
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.push(LockStatus.SECUREMODE)
    await hass.async_block_till_done()
    assert not _writes(state_events)

    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 4))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.attributes["changed_by"] == "Keypad slot 4"
    assert len(_writes(state_events)) == 1


@pytest.mark.usefixtures("entry")
async def test_activity_not_matching_hold_ignored(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a stale activity for the old state does not release the hold."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.MANUAL))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    assert not activity_events
    await _expire_hold(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    assert hass.states.get(ENTITY_ID).attributes.get("changed_by") is None


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("status", "source", "expected"),
    [
        pytest.param(
            LockStatus.LOCKED, LockOperationSource.MANUAL, "Manual", id="match"
        ),
        pytest.param(
            LockStatus.SECUREMODE, LockOperationSource.REMOTE, "Remote", id="secure"
        ),
        pytest.param(LockStatus.UNLOCKED, LockOperationSource.MANUAL, None, id="stale"),
        pytest.param(
            LockStatus.LOCKED, LockOperationSource.UNKNOWN, None, id="unknown"
        ),
        pytest.param(
            LockStatus.LOCKING, LockOperationSource.MANUAL, None, id="transient"
        ),
    ],
)
async def test_activity_outside_hold(
    hass: HomeAssistant,
    mock_lock: MockLock,
    status: LockStatus,
    source: LockOperationSource,
    expected: str | None,
) -> None:
    """Test activities outside a hold only update changed_by for the current state."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.fire(_activity(status, source))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes.get("changed_by") == expected
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_door_activity_ignored(hass: HomeAssistant, mock_lock: MockLock) -> None:
    """Test door activity is ignored."""
    mock_lock.fire(DoorActivity(dt_util.utcnow(), DoorStatus.OPENED))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes.get("changed_by") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_event_entity_is_main_lock_regardless_of_listener_order(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the event names the main lock even when the alias handles it first."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    listeners = sorted(
        entry.runtime_data.activity_listeners,
        key=lambda listener: not listener.__self__._secure_mode,
    )
    mock_lock.push(LockStatus.UNLOCKED)
    activity = _activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL)
    for listener in listeners:
        listener(activity)
    await _settle(hass, freezer)
    assert len(activity_events) == 1
    assert activity_events[0].data["entity_id"] == ENTITY_ID


@pytest.mark.usefixtures("entry")
async def test_event_entity_falls_back_to_alias_without_main_lock(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the alias owns the event when the main lock is not added."""
    entity_registry.async_update_entity(SECURE_ENTITY_ID, disabled_by=None)
    entity_registry.async_update_entity(
        ENTITY_ID, disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    await hass.async_block_till_done()
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    assert len(activity_events) == 1
    assert activity_events[0].data["entity_id"] == SECURE_ENTITY_ID


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_secure_mode_entity_shares_one_event(
    hass: HomeAssistant,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test both lock entities share a single event and context."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)
    assert len(activity_events) == 1
    assert hass.states.get(ENTITY_ID).context.id == activity_events[0].context.id
    assert hass.states.get(SECURE_ENTITY_ID).state == "unlocked"
    assert hass.states.get(SECURE_ENTITY_ID).context.id == activity_events[0].context.id


async def test_removal_cancels_hold(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading cancels a pending hold."""
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unavailable"
    await _expire_hold(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "unavailable"


@pytest.fixture
def unavailable_callbacks() -> Generator[list[Callable[[Any], None]]]:
    """Capture the bluetooth unavailable callbacks the entities register."""
    callbacks: list[Callable[[Any], None]] = []

    def _track(
        hass: HomeAssistant, callback: Callable[[Any], None], address: str
    ) -> Callable[[], None]:
        callbacks.append(callback)
        return lambda: None

    with patch(
        "homeassistant.components.yalexs_ble.entity.bluetooth.async_track_unavailable",
        side_effect=_track,
    ):
        yield callbacks


async def test_unavailable_cancels_hold(
    hass: HomeAssistant,
    unavailable_callbacks: list[Callable[[Any], None]],
    mock_lock: MockLock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the device going unavailable drops the held state."""
    mock_lock.push(LockStatus.UNLOCKED)
    assert hass.states.get(ENTITY_ID).state == "locked"
    for callback in unavailable_callbacks:
        callback(MagicMock())
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unavailable"
    await _expire_hold(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "unavailable"


@pytest.mark.usefixtures("entry")
async def test_activity_callback_registered_before_start(
    mock_lock: MockLock,
) -> None:
    """Test the activity callback is registered once, before start."""
    assert mock_lock.calls == ["register", "start"]
    mock_lock.push_lock.register_activity_callback.assert_called_once()


async def test_unload_unregisters_and_remove_deletes_store(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    """Test unload unregisters the activity callback and removal deletes names."""
    await _call(
        hass,
        "set_lock_credential",
        {"credential_data": "1234", "credential_index": 2, "name": "Temp"},
    )
    key = STORAGE_KEY.format(entry.entry_id)
    assert key in hass_storage

    listeners = entry.runtime_data.activity_listeners
    assert listeners

    await hass.config_entries.async_unload(entry.entry_id)
    mock_lock.unregister_activity.assert_called_once_with()
    assert not listeners

    await hass.config_entries.async_remove(entry.entry_id)
    assert key not in hass_storage


@pytest.mark.usefixtures("entry")
@pytest.mark.parametrize(
    ("source", "slot", "name", "expected_name", "message", "master_code"),
    [
        pytest.param(
            "pin", 205, "Test", "Test", "keypad code Test used", False, id="pin_named"
        ),
        pytest.param(
            "pin",
            205,
            None,
            "Keypad slot 205",
            "keypad slot 205 used",
            False,
            id="pin_slot",
        ),
        pytest.param(
            "pin", None, None, "Keypad", "keypad used", False, id="pin_no_slot"
        ),
        pytest.param(
            "pin",
            None,
            None,
            "Master code",
            "master code used",
            True,
            id="master_unnamed",
        ),
        pytest.param(
            "pin",
            None,
            "Admin",
            "Admin",
            "keypad code Admin used",
            True,
            id="master_named",
        ),
        pytest.param(
            "manual", None, None, "Manual", "operated manually", False, id="manual"
        ),
        pytest.param(
            "auto_lock", None, None, "Auto lock", "auto locked", False, id="auto_lock"
        ),
        pytest.param(
            "remote", None, None, "Remote", "operated remotely", False, id="remote"
        ),
        pytest.param("other", None, None, "other", "other", False, id="unknown_source"),
    ],
)
async def test_logbook_describes_activity(
    hass: HomeAssistant,
    source: str,
    slot: int | None,
    name: str | None,
    expected_name: str,
    message: str,
    master_code: bool,
) -> None:
    """Test the logbook describes lock activity events."""
    hass.config.components.add("recorder")
    assert await async_setup_component(hass, "logbook", {})
    await hass.async_block_till_done()

    (logbook_entry,) = mock_humanify(
        hass,
        [
            MockRow(
                EVENT_LOCK_ACTIVITY,
                {
                    "entity_id": ENTITY_ID,
                    "source": source,
                    "slot": slot,
                    "master_code": master_code,
                    "name": name,
                },
            )
        ],
    )

    assert logbook_entry["domain"] == DOMAIN
    assert logbook_entry["name"] == expected_name
    assert logbook_entry["message"] == message
    assert logbook_entry["entity_id"] == ENTITY_ID


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        pytest.param(ENTITY_ID, "lock", id="lock"),
        pytest.param(SECURE_ENTITY_ID, "securemode", id="secure_mode"),
    ],
)
async def test_lock_service(
    hass: HomeAssistant, mock_lock: MockLock, entity_id: str, method: str
) -> None:
    """Test locking calls the matching library method."""
    mock_lock.push_lock.securemode = AsyncMock()
    await hass.services.async_call(
        "lock", "lock", {"entity_id": entity_id}, blocking=True
    )
    getattr(mock_lock.push_lock, method).assert_awaited_once_with()


def _call_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    **kwargs: Any,
) -> Any:
    """Call a yalexs_ble lock service targeting the whole device."""
    device = device_registry.async_get_device_by_connection(
        ("bluetooth", YALE_ACCESS_LOCK_DISCOVERY_INFO.address), entry.entry_id
    )
    return hass.services.async_call(
        DOMAIN,
        service,
        {"device_id": device.id, "credential_type": "pin", **data},
        blocking=True,
        **kwargs,
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_target_set_credential_runs_once(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lock: MockLock,
    entry: MockConfigEntry,
) -> None:
    """Test targeting both lock entities sets the PIN and name once."""
    with patch.object(
        CredentialNames,
        "async_set",
        autospec=True,
        side_effect=CredentialNames.async_set,
    ) as name_set:
        await _call_device(
            hass,
            device_registry,
            entry,
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 5, "name": "Jesse"},
        )

    mock_lock.push_lock.set_keycode.assert_awaited_once_with(5, "1234")
    assert name_set.await_count == 1
    assert entry.runtime_data.credential_names.get(5) == "Jesse"
    assert not entry.runtime_data.credential_operations


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_target_clear_credential_runs_once(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lock: MockLock,
    entry: MockConfigEntry,
) -> None:
    """Test targeting both lock entities clears the PIN and name once."""
    with patch.object(
        CredentialNames,
        "async_remove",
        autospec=True,
        side_effect=CredentialNames.async_remove,
    ) as name_remove:
        await _call_device(
            hass,
            device_registry,
            entry,
            "clear_lock_credential",
            {"credential_index": 5},
        )

    mock_lock.push_lock.clear_keycode.assert_awaited_once_with(5)
    assert name_remove.await_count == 1


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_target_status_shared(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lock: MockLock,
    entry: MockConfigEntry,
) -> None:
    """Test both lock entities report the same single status read."""
    mock_lock.push_lock.get_keycode.return_value = "4321"
    response = await _call_device(
        hass,
        device_registry,
        entry,
        "get_lock_credential_status",
        {"credential_index": 9},
        return_response=True,
    )

    mock_lock.push_lock.get_keycode.assert_awaited_once_with(9)
    expected = {"credential_exists": True, "name": None}
    assert response == {ENTITY_ID: expected, SECURE_ENTITY_ID: expected}


@pytest.mark.usefixtures("entry")
async def test_parallel_set_credential_different_slots_both_run(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test concurrent calls sharing a context but not data both run."""
    context = Context()
    await asyncio.gather(
        *(
            _call(
                hass,
                "set_lock_credential",
                {"credential_data": "1234", "credential_index": slot},
                context=context,
            )
            for slot in (1, 2)
        )
    )

    assert sorted(c.args for c in mock_lock.push_lock.set_keycode.await_args_list) == [
        (1, "1234"),
        (2, "1234"),
    ]
    assert not hass.config_entries.async_entries(DOMAIN)[
        0
    ].runtime_data.credential_operations


@pytest.mark.usefixtures("entry")
async def test_parallel_status_different_slots_both_run(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test concurrent status reads for different slots return their own result."""
    mock_lock.push_lock.get_keycode.side_effect = {1: "1234"}.get
    context = Context()
    first, second = await asyncio.gather(
        *(
            _call(
                hass,
                "get_lock_credential_status",
                {"credential_index": slot},
                context=context,
                return_response=True,
            )
            for slot in (1, 2)
        )
    )

    assert first[ENTITY_ID] == {"credential_exists": True, "name": None}
    assert second[ENTITY_ID] == {"credential_exists": False, "name": None}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("service", "data", "method", "message"),
    [
        pytest.param(
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 5},
            "set_keycode",
            "Failed to communicate",
            id="set",
        ),
        pytest.param(
            "clear_lock_credential",
            {"credential_index": 5},
            "clear_keycode",
            "Failed to communicate",
            id="clear",
        ),
    ],
)
async def test_device_target_failure_runs_once(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    service: str,
    data: dict[str, Any],
    method: str,
    message: str,
) -> None:
    """Test a failure is raised once, translated, and not retried per entity."""
    getattr(mock_lock.push_lock, method).side_effect = YaleXSBLEError("boom")
    with pytest.raises(HomeAssistantError, match=message):
        await _call_device(hass, device_registry, entry, service, data)

    getattr(mock_lock.push_lock, method).assert_awaited_once()
    assert not entry.runtime_data.credential_operations


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_device_target_invalid_pin(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_lock: MockLock,
    entry: MockConfigEntry,
) -> None:
    """Test PIN validation still raises when both entities are targeted."""
    with pytest.raises(ServiceValidationError, match="PIN"):
        await _call_device(
            hass,
            device_registry,
            entry,
            "set_lock_credential",
            {"credential_data": "12", "credential_index": 5},
        )
    mock_lock.push_lock.set_keycode.assert_not_awaited()


@pytest.mark.usefixtures("entry")
async def test_hold_timeout_drops_credential_action_context(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test an unattributed change does not carry a recent credential action context."""
    context = Context(user_id=hass_admin_user.id, parent_id="parent-id")
    await _call(
        hass,
        "clear_lock_credential",
        {"credential_index": 3},
        context=context,
    )

    mock_lock.push(LockStatus.UNLOCKED)
    await _expire_hold(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.context.id != context.id
    assert state.context.parent_id is None
    assert state.context.user_id is None


@pytest.mark.usefixtures("entry")
async def test_transitional_state_drops_credential_action_context(
    hass: HomeAssistant, hass_admin_user: MockUser, mock_lock: MockLock
) -> None:
    """Test an unheld write after a credential action does not carry its context."""
    context = Context(user_id=hass_admin_user.id)
    await _call(
        hass,
        "clear_lock_credential",
        {"credential_index": 3},
        context=context,
    )

    mock_lock.push(LockStatus.UNLOCKING)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocking"
    assert state.context.id != context.id
    assert state.context.user_id is None


@pytest.mark.usefixtures("entry")
async def test_cancelled_ha_operation_clears_expectation(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a cancelled library call does not leave an expected operation behind."""
    mock_lock.push_lock.unlock.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await hass.services.async_call(
            "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
        )

    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_backlog_attributes_to_newest_matching_activity(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test an offline backlog attributes the held state to its newest match."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    for status, slot in (
        (LockStatus.UNLOCKED, 1),
        (LockStatus.LOCKED, 2),
        (LockStatus.UNLOCKED, 3),
    ):
        mock_lock.fire(_activity(status, LockOperationSource.PIN, slot))
        freezer.tick(timedelta(seconds=0.3))
        async_fire_time_changed_exact(hass)
        await hass.async_block_till_done()
        assert hass.states.get(ENTITY_ID).state == "locked"
    assert not activity_events

    await _settle(hass, freezer)

    for entity_id in (ENTITY_ID, SECURE_ENTITY_ID):
        state = hass.states.get(entity_id)
        assert state.state == "unlocked"
        assert state.context.id == activity_events[0].context.id
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"
    assert len(activity_events) == 1
    assert activity_events[0].data["slot"] == 3


@pytest.mark.usefixtures("entry")
async def test_hold_deadline_attributes_to_candidate(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a continuing backlog cannot extend the settle past the hold deadline."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    for _ in range(3):
        freezer.tick(timedelta(seconds=0.5))
        async_fire_time_changed_exact(hass)
        mock_lock.fire(DoorActivity(dt_util.utcnow(), DoorStatus.OPENED))
        await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"

    freezer.tick(timedelta(seconds=0.6))
    async_fire_time_changed_exact(hass)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"
    assert len(activity_events) == 1


@pytest.mark.usefixtures("entry")
async def test_candidate_dropped_when_held_state_changes(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a candidate for a superseded held state is not used."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    mock_lock.push(LockStatus.SECUREMODE)
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "locked"

    await _expire_hold(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert "changed_by" not in state.attributes
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_held_state_change_keeps_matching_candidate(
    hass: HomeAssistant, mock_lock: MockLock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a held state update that still matches keeps its candidate."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    mock_lock.push(LockStatus.UNLOCKED, percentage=50)
    await _settle(hass, freezer)
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


async def test_removal_cancels_settle(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test unloading cancels a pending settle timer."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "unavailable"
    assert not activity_events


async def test_unavailable_cancels_settle(
    hass: HomeAssistant,
    unavailable_callbacks: list[Callable[[Any], None]],
    mock_lock: MockLock,
    entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the device going unavailable drops the candidate and settle timer."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    for callback in unavailable_callbacks:
        callback(MagicMock())
    await hass.async_block_till_done()
    await _settle(hass, freezer)
    assert hass.states.get(ENTITY_ID).state == "unavailable"
    assert not activity_events


@pytest.mark.usefixtures("entry")
async def test_transitional_state_keeps_newer_service_context(
    hass: HomeAssistant,
    hass_admin_user: MockUser,
    mock_lock: MockLock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a Home Assistant lock action's context survives an earlier activity."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await _settle(hass, freezer)

    mock_lock.push_lock.lock.side_effect = lambda: mock_lock.push(LockStatus.LOCKING)
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "lock", "lock", {"entity_id": ENTITY_ID}, blocking=True, context=context
    )
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "locking"
    assert state.context.id == context.id
    assert state.context.user_id == hass_admin_user.id


@pytest.mark.usefixtures("entry")
async def test_overlapping_lock_action_keeps_its_context(
    hass: HomeAssistant, hass_admin_user: MockUser, mock_lock: MockLock
) -> None:
    """Test a lock action during a credential action keeps its initiating user."""
    release = asyncio.Event()
    started = asyncio.Event()

    async def slow_clear(slot: int) -> None:
        started.set()
        await release.wait()

    mock_lock.push_lock.clear_keycode.side_effect = slow_clear
    credential_task = hass.async_create_task(
        _call(hass, "clear_lock_credential", {"credential_index": 3})
    )
    await started.wait()

    lock_context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True, context=lock_context
    )
    release.set()
    await credential_task

    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.context.id == lock_context.id
    assert state.context.user_id == hass_admin_user.id


@pytest.mark.usefixtures("entry")
async def test_cancelled_set_credential_removes_name(
    hass: HomeAssistant, mock_lock: MockLock, entry: MockConfigEntry
) -> None:
    """Test cancelling a set after programming started drops the old name."""
    entry.runtime_data.credential_names._names["3"] = "Guest"
    started = asyncio.Event()

    async def hang(slot: int, pin: str) -> None:
        started.set()
        await asyncio.Event().wait()

    mock_lock.push_lock.set_keycode.side_effect = hang
    task = hass.async_create_task(
        _call(
            hass,
            "set_lock_credential",
            {"credential_data": "1234", "credential_index": 3, "name": "New"},
        )
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert entry.runtime_data.credential_names.get(3) is None
    assert not entry.runtime_data.credential_operations


@pytest.mark.usefixtures("entry")
async def test_renamed_main_lock_owns_activity_events(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test activity events follow the main lock after an entity_id change."""
    new_entity_id = "lock.back_door"
    entity_registry.async_update_entity(ENTITY_ID, new_entity_id=new_entity_id)
    await hass.async_block_till_done()

    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await _settle(hass, freezer)

    assert len(activity_events) == 1
    assert activity_events[0].data["entity_id"] == new_entity_id
