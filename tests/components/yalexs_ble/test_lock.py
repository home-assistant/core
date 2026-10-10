"""Test the Yale Access Bluetooth lock credential services and changed_by."""

from collections.abc import AsyncGenerator, Callable
from dataclasses import replace
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakDBusError, BleakError
from bleak_retry_connector import BleakNotFoundError, BleakOutOfConnectionSlotsError
from freezegun.api import FrozenDateTimeFactory
import probatio
import pytest
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

from homeassistant.components.yalexs_ble.const import (
    ACTIVITY_HOLD_SECONDS,
    CONF_KEY,
    CONF_LOCAL_NAME,
    CONF_SLOT,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    HA_OPERATION_TIMEOUT_SECONDS,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, EVENT_STATE_CHANGED
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import (
    HomeAssistantError,
    ServiceValidationError,
    Unauthorized,
)
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import YALE_ACCESS_LOCK_DISCOVERY_INFO

from tests.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
)
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
def mock_lock() -> MockLock:
    """Return a mocked lock."""
    return MockLock()


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
    await hass.async_block_till_done()
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
            "already in use",
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
    ("error", "name_kept"),
    [
        pytest.param(
            KeycodeError("clear_keycode", OperationError.KEYCODE_NOSPACE),
            True,
            id="clear_failed",
        ),
        pytest.param(
            KeycodeError("commit_keycode", OperationError.KEYCODE_NOSPACE),
            False,
            id="commit_failed",
        ),
        pytest.param(BleakError("gone"), False, id="bleak"),
    ],
)
async def test_failed_set_credential_name_handling(
    hass: HomeAssistant,
    mock_lock: MockLock,
    entry: MockConfigEntry,
    error: Exception,
    name_kept: bool,
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
    assert entry.runtime_data.credential_names.get(3) == (
        "Guest" if name_kept else None
    )


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
    await hass.async_block_till_done()

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
) -> None:
    """Test a master code unlock is attributed with a flag instead of a slot."""
    entry.runtime_data.master_code_name = master_code_name
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(
        _activity(LockStatus.UNLOCKED, LockOperationSource.PIN, KEYPAD_MASTER_CODE_SLOT)
    )
    await hass.async_block_till_done()

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
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
    cause_id = hass.states.get(ENTITY_ID).context.id

    mock_lock.push(LockStatus.LOCKED)
    await _expire_hold(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.context.id != cause_id
    assert "changed_by" not in state.attributes


@pytest.mark.usefixtures("entry")
async def test_second_activity_not_treated_as_ha_initiated(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test a change right after an attributed one is still held."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await hass.async_block_till_done()
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)

    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entry")
async def test_external_change_after_ha_operation_held(
    hass: HomeAssistant, mock_lock: MockLock
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
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "locked"
    assert state.attributes["changed_by"] == "Keypad slot 3"


@pytest.mark.usefixtures("entry")
async def test_opposite_change_during_ha_operation_held(
    hass: HomeAssistant, mock_lock: MockLock
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
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Manual"


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_noop_ha_operation_does_not_misattribute_later_change(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test an HA command that changes nothing does not claim a later change."""
    mock_lock.push_lock.securemode = AsyncMock()
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await hass.async_block_till_done()

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": ENTITY_ID}, blocking=True
    )
    mock_lock.push(LockStatus.LOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "unlocked"
    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 3))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"

    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == "locked"
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 4))
    await hass.async_block_till_done()
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
) -> None:
    """Test a failing library call does not leave an expected operation behind."""
    mock_lock.push(start)
    mock_lock.fire(_activity(start, LockOperationSource.MANUAL))
    await hass.async_block_till_done()
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
    hass: HomeAssistant, mock_lock: MockLock, service: str, data: dict[str, Any]
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
    await hass.async_block_till_done()
    state = hass.states.get(ENTITY_ID)
    assert state.state == "unlocked"
    assert state.attributes["changed_by"] == "Keypad slot 3"
    assert len(activity_events) == 1


@pytest.mark.usefixtures("entry")
async def test_changed_by_cleared_on_ha_initiated_change(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test an HA initiated change drops the previous keypad attribution."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await hass.async_block_till_done()
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
    await hass.async_block_till_done()
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
    hass: HomeAssistant, mock_lock: MockLock, status: LockStatus, state: str
) -> None:
    """Test transitional and fault states drop the previous attribution."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes["changed_by"] == "Keypad slot 3"

    mock_lock.push(status)
    await hass.async_block_till_done()
    result = hass.states.get(ENTITY_ID)
    assert result.state == state
    assert "changed_by" not in result.attributes


@pytest.mark.usefixtures("entry")
async def test_changed_by_kept_on_battery_update(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test an update that keeps the lock status keeps the attribution."""
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.PIN, 3))
    await hass.async_block_till_done()

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
    hass: HomeAssistant, mock_lock: MockLock
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
    await hass.async_block_till_done()
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
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test later callbacks update the held state and secure mode matches locked."""
    state_events = async_capture_events(hass, EVENT_STATE_CHANGED)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.push(LockStatus.SECUREMODE)
    await hass.async_block_till_done()
    assert not _writes(state_events)

    mock_lock.fire(_activity(LockStatus.LOCKED, LockOperationSource.PIN, 4))
    await hass.async_block_till_done()
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "entry")
async def test_secure_mode_entity_shares_one_event(
    hass: HomeAssistant, mock_lock: MockLock
) -> None:
    """Test both lock entities share a single event and context."""
    activity_events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    mock_lock.push(LockStatus.UNLOCKED)
    mock_lock.fire(_activity(LockStatus.UNLOCKED, LockOperationSource.MANUAL))
    await hass.async_block_till_done()
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

    await hass.config_entries.async_unload(entry.entry_id)
    mock_lock.unregister_activity.assert_called_once_with()

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
