"""Test the ISEO Argo BLE access log event entity."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from iseo_argo_ble import IseoAuthError, IseoConnectionError, LogEntry
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.components.iseo_argo_ble.const import DOMAIN
from homeassistant.components.iseo_argo_ble.lock import (
    _ACCESS_LOG_DEBOUNCE,
    _POLL_INTERVAL,
    SERVICE_READ_ACCESS_LOG,
)
from homeassistant.components.lock import DOMAIN as LOCK_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform

ENTITY_ID = "event.iseo_lock_access_log"
LOCK_ENTITY_ID = "lock.iseo_lock"

# 8 = Door Open, 5 = Wrong PIN, 90 = Hardware fault, 3 = not an access event.
CODE_OPENED = 8
CODE_WRONG_PIN = 5
CODE_HARDWARE_FAULT = 90
CODE_IGNORED = 3


def _log_entry(
    event_code: int,
    timestamp: datetime,
    extra_description: str = "",
    user_info: str = "",
) -> LogEntry:
    """Return an access log entry as the lock would report it."""
    return LogEntry(
        event_code=event_code,
        extra_description=extra_description,
        user_info=user_info,
        list_code=0,
        battery=100,
        timestamp=timestamp,
    )


def _lock_state(door_closed: bool) -> MagicMock:
    """Return a lock state reporting the given door status."""
    return MagicMock(door_closed=door_closed, firmware_info="FW:  1.2.3")


async def _open_the_door(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, mock_iseo_client: MagicMock
) -> None:
    """Let the lock report an open door and run the debounced log read."""
    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=_ACCESS_LOG_DEBOUNCE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test the access log entity and the event types it reports."""
    with patch("homeassistant.components.iseo_argo_ble.PLATFORMS", [Platform.EVENT]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_door_open_reports_the_log_entry(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a door open makes the lock read its log and report who opened it."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    opened_at = datetime(2026, 9, 2, 14, 3, 11, tzinfo=UTC)
    mock_iseo_client.gw_read_unread_logs.return_value = [
        _log_entry(CODE_OPENED, opened_at, extra_description="Federico")
    ]

    await _open_the_door(hass, freezer, mock_iseo_client)

    mock_iseo_client.gw_read_unread_logs.assert_called_once()
    state = hass.states.get(ENTITY_ID)
    assert state.attributes[ATTR_EVENT_TYPE] == "opened"
    assert state.attributes["opened_by"] == "Federico"
    assert state.attributes["event_code"] == CODE_OPENED
    assert state.attributes["description"] == "Door Open"
    assert state.attributes["occurred_at"] == opened_at.isoformat()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_only_the_newest_of_each_kind_is_reported(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a backlog is not replayed: one event per kind, newest last.

    A read drains everything unread, which after a quiet spell can be a long
    history. Reporting all of it would look like it had all just happened.
    """
    await setup_integration(hass, mock_config_entry)

    base = datetime(2026, 9, 2, 9, 0, tzinfo=UTC)
    mock_iseo_client.gw_read_unread_logs.return_value = [
        _log_entry(CODE_WRONG_PIN, base, user_info="keypad"),
        _log_entry(CODE_OPENED, base + timedelta(minutes=1), extra_description="Alice"),
        _log_entry(CODE_OPENED, base + timedelta(minutes=2), extra_description="Bob"),
        _log_entry(CODE_IGNORED, base + timedelta(minutes=3)),
    ]

    await _open_the_door(hass, freezer, mock_iseo_client)

    state = hass.states.get(ENTITY_ID)
    # Reported oldest first, so the entity settles on the most recent entry.
    assert state.attributes[ATTR_EVENT_TYPE] == "opened"
    assert state.attributes["opened_by"] == "Bob"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_entries_without_an_access_event_are_ignored(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test log entries that are not access events report nothing."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.gw_read_unread_logs.return_value = [
        _log_entry(CODE_IGNORED, datetime(2026, 9, 2, 9, 0, tzinfo=UTC))
    ]

    await _open_the_door(hass, freezer, mock_iseo_client)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_unlock_reads_the_log(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test unlocking from Home Assistant also reads the log.

    Such an unlock never shows up as a door open — the entity is marked
    unlocked before the poll sees the door move.
    """
    await setup_integration(hass, mock_config_entry)
    mock_iseo_client.gw_read_unread_logs.return_value = [
        _log_entry(
            CODE_OPENED,
            datetime(2026, 9, 2, 14, 3, 11, tzinfo=UTC),
            extra_description="Home Assistant",
        )
    ]

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        await hass.services.async_call(
            LOCK_DOMAIN,
            "unlock",
            {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=_ACCESS_LOG_DEBOUNCE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID).attributes["opened_by"] == "Home Assistant"


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_read_access_log_action(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the action reads the log without waiting for a door open."""
    await setup_integration(hass, mock_config_entry)
    mock_iseo_client.gw_read_unread_logs.return_value = [
        _log_entry(CODE_HARDWARE_FAULT, datetime(2026, 9, 2, 14, 3, 11, tzinfo=UTC))
    ]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_ACCESS_LOG,
        {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
        blocking=True,
    )

    mock_iseo_client.gw_read_unread_logs.assert_called_once()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_EVENT_TYPE] == "fault"


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_read_access_log_action_without_ble_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
) -> None:
    """Test the action reports an error while the lock is out of range."""
    await setup_integration(hass, mock_config_entry)

    with (
        patch(
            "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_READ_ACCESS_LOG,
            {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
            blocking=True,
        )


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_repeated_opens_read_the_log_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test door activity inside the debounce window collapses into one read."""
    await setup_integration(hass, mock_config_entry)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        for _ in range(2):
            await hass.services.async_call(
                LOCK_DOMAIN,
                "unlock",
                {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
                blocking=True,
            )
            await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=_ACCESS_LOG_DEBOUNCE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_iseo_client.gw_read_unread_logs.assert_called_once()


@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_action_supersedes_a_pending_read(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
) -> None:
    """Test the action cancels a debounced read rather than doubling it."""
    await setup_integration(hass, mock_config_entry)

    with patch("homeassistant.components.iseo_argo_ble.lock._RELOCK_POLL_DELAY", 0):
        await hass.services.async_call(
            LOCK_DOMAIN,
            "unlock",
            {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
            blocking=True,
        )
        await hass.async_block_till_done()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_READ_ACCESS_LOG,
        {ATTR_ENTITY_ID: LOCK_ENTITY_ID},
        blocking=True,
    )

    freezer.tick(timedelta(seconds=_ACCESS_LOG_DEBOUNCE))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_iseo_client.gw_read_unread_logs.assert_called_once()


@pytest.mark.usefixtures("mock_iseo_client", "mock_derive_private_key")
async def test_read_is_skipped_when_the_lock_goes_out_of_range(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_ble_device: MagicMock,
    mock_iseo_client: MagicMock,
) -> None:
    """Test a debounced read is dropped if the lock is gone by the time it runs."""
    await setup_integration(hass, mock_config_entry)

    mock_iseo_client.read_state.return_value = _lock_state(door_closed=False)
    freezer.tick(_POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.iseo_argo_ble.lock.async_ble_device_from_address",
        return_value=None,
    ):
        freezer.tick(timedelta(seconds=_ACCESS_LOG_DEBOUNCE))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    mock_iseo_client.gw_read_unread_logs.assert_not_called()
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.parametrize(
    "error",
    [IseoAuthError("rejected"), IseoConnectionError("no link"), TimeoutError],
)
@pytest.mark.usefixtures("mock_derive_private_key", "mock_ble_device")
async def test_failed_read_reports_nothing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_iseo_client: MagicMock,
    error: Exception,
) -> None:
    """Test a failed log read leaves the entity alone.

    The entries stay unread on the lock, so the next read picks them up.
    """
    await setup_integration(hass, mock_config_entry)
    mock_iseo_client.gw_read_unread_logs.side_effect = error

    await _open_the_door(hass, freezer, mock_iseo_client)

    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN
