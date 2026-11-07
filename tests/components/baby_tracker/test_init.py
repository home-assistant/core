"""Tests for setup, sync, storage, unload, and translated errors."""

from datetime import timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pybabytracker import BabyTrackerConnectionError, ProtocolError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.baby_tracker.const import CONF_DEVICE_UUID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DIAPER, NOW, tick
from .factories import DEVICE_A, DEVICE_B, at
from .fake_server import FakeServer


@pytest.fixture(autouse=True)
def _start_at_now(freezer: FrozenDateTimeFactory) -> None:
    """Freeze the clock at NOW before anything is set up.

    Timers scheduled at setup then share the clock the tests move, so moving it forward and
    ticking reaches them the way it does in core's tests.
    """
    freezer.move_to(NOW)


def _storage_key(entry: MockConfigEntry) -> str:
    return f"{DOMAIN}.{entry.entry_id}"


async def test_setup_loads_the_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the entry loads."""
    assert init_integration.state is ConfigEntryState.LOADED


async def test_setup_backfills_each_device_from_the_start(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test the first setup reads each device's log from the start."""
    assert server.reads_from_start() == [(DEVICE_A, 0)]
    assert hass.states.get(DIAPER).state != "unknown"


async def test_the_client_signs_in_as_its_own_device_named_home_assistant(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test the client signs in as the entry's own device."""
    sign_in = server.sign_ins[0]
    assert sign_in["device_name"] == "Home Assistant"
    assert sign_in["device_uuid"] == init_integration.data[CONF_DEVICE_UUID]


async def test_the_client_uses_its_own_http_session(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test the client gets an HTTP session of its own."""
    session = server.clients[0].kwargs["session"]
    assert session is not async_get_clientsession(hass)
    assert not session.closed


@pytest.mark.parametrize(
    "error",
    [BabyTrackerConnectionError("offline"), ProtocolError("odd")],
    ids=["connection", "protocol"],
)
async def test_a_failed_first_sync_retries_later_and_closes_the_client(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
    error: Exception,
) -> None:
    """Test a failed first sync retries with a translated reason, and leaves no client open."""
    server.request_error = error
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "sync_failed_update"
    assert (
        str(error) in mock_config_entry.error_reason_translation_placeholders["error"]
    )
    assert server.clients
    assert server.open_clients == []
    assert all(client.kwargs["session"].closed for client in server.clients)


async def test_setup_retries_and_then_loads_once_the_server_is_back(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, server: FakeServer
) -> None:
    """Test setup loads on a retry once the service is back."""
    server.sign_in_error = BabyTrackerConnectionError("down")
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    server.sign_in_error = None
    await tick(hass, minutes=2)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.state is ConfigEntryState.LOADED


async def test_syncs_run_every_five_minutes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the account syncs every five minutes."""
    assert init_integration.runtime_data.update_interval == timedelta(minutes=5)


@pytest.mark.parametrize(
    "error",
    [BabyTrackerConnectionError("offline"), ProtocolError("odd")],
    ids=["connection", "protocol"],
)
async def test_an_update_failure_makes_entities_unavailable_then_recovers(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    server: FakeServer,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """Test a failed sync makes the entities unavailable, until one works."""
    before = hass.states.get(DIAPER).state
    server.request_error = error
    await tick(hass)
    assert hass.states.get(DIAPER).state == STATE_UNAVAILABLE
    assert init_integration.state is ConfigEntryState.LOADED
    assert f"Couldn't sync with the service: {error}" in caplog.text

    server.request_error = None
    await tick(hass)
    assert hass.states.get(DIAPER).state == before


async def test_the_synced_state_is_saved(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    """Test the sync state is saved."""
    saved = hass_storage[_storage_key(init_integration)]["data"]
    assert saved["last_seen"] == {DEVICE_A: 2}
    assert len(saved["records"]) == 2


async def test_new_records_are_saved_after_a_sync(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    server: FakeServer,
    hass_storage: dict[str, Any],
) -> None:
    """Test a sync that finds new records saves them."""
    server.add_record(
        DEVICE_B, "Diaper", "D5000000-0000-4000-8000-000000000001", when=at(45)
    )
    await tick(hass)
    saved = hass_storage[_storage_key(init_integration)]["data"]
    assert saved["last_seen"] == {DEVICE_A: 2, DEVICE_B: 1}


async def test_a_restart_loads_the_saved_state_and_does_not_reload_history(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test a restart loads the saved state instead of every log."""
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    server.transaction_reads.clear()

    assert await hass.config_entries.async_setup(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED
    assert server.transaction_reads == []
    assert hass.states.get(DIAPER).state == at(0).isoformat()


@pytest.mark.parametrize(
    "corrupt",
    [
        {"version": 99, "last_seen": {}, "records": []},
        {"garbage": True},
        "not a mapping",
        {
            "version": 3,
            "last_seen": {DEVICE_A: 2},
            "records": [{"payload": {"no": "id"}}],
        },
    ],
    ids=["unsupported-version", "missing-keys", "wrong-type", "bad-record"],
)
async def test_corrupt_storage_falls_back_to_a_fresh_backfill_with_a_warning(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
    hass_storage: dict[str, Any],
    caplog: pytest.LogCaptureFixture,
    corrupt: object,
) -> None:
    """Test a saved state that can't be read is replaced by a fresh backfill, with a warning."""
    key = _storage_key(mock_config_entry)
    hass_storage[key] = {"version": 1, "minor_version": 1, "key": key, "data": corrupt}
    mock_config_entry.add_to_hass(hass)

    with caplog.at_level(logging.WARNING):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert server.reads_from_start() == [(DEVICE_A, 0)]
    assert hass.states.get(DIAPER).state == at(0).isoformat()
    assert any(
        record.levelno == logging.WARNING
        and "saved sync state" in record.getMessage().lower()
        for record in caplog.records
    )
    assert hass_storage[key]["data"]["last_seen"] == {
        DEVICE_A: 2
    }  # replaced by a good copy


async def test_a_saved_state_the_store_cannot_load_falls_back_to_a_fresh_backfill(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a store that fails to load leads to a fresh backfill, with a warning."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.helpers.storage.Store.async_load",
            side_effect=HomeAssistantError("unreadable"),
        ),
        caplog.at_level(logging.WARNING),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert server.reads_from_start() == [(DEVICE_A, 0)]
    assert hass.states.get(DIAPER).state == at(0).isoformat()
    assert "saved sync state couldn't be read (unreadable)" in caplog.text


async def test_removing_the_entry_removes_its_saved_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, hass_storage: dict[str, Any]
) -> None:
    """Test removing the entry deletes its saved state."""
    key = _storage_key(init_integration)
    assert key in hass_storage

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert key not in hass_storage


async def test_unloading_the_entry(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    server: FakeServer,
    hass_storage: dict[str, Any],
) -> None:
    """Test unloading stops the syncs, closes the client, and keeps the saved state."""
    session = server.clients[0].kwargs["session"]
    assert len(server.open_clients) == 1

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(DIAPER).state == STATE_UNAVAILABLE
    assert server.open_clients == []
    assert session.closed
    assert _storage_key(init_integration) in hass_storage

    calls = server.device_list_calls
    await tick(hass, minutes=30)
    assert server.device_list_calls == calls


async def test_an_entry_can_be_reloaded(
    hass: HomeAssistant, init_integration: MockConfigEntry, server: FakeServer
) -> None:
    """Test reloads set the entry up again and leave exactly one client open."""
    for _ in range(2):
        assert await hass.config_entries.async_reload(init_integration.entry_id)
        await hass.async_block_till_done()

    assert init_integration.state is ConfigEntryState.LOADED
    assert hass.states.get(DIAPER).state == at(0).isoformat()
    assert len(server.open_clients) == 1


async def test_a_failing_save_does_not_replace_the_sync_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    server: FakeServer,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed save is logged and the sync's error still decides the state."""
    # Device A syncs (so there is progress to save), then device B fails.
    server.add_record(
        DEVICE_B, "Diaper", "D9000000-0000-4000-8000-000000000001", when=at(5)
    )
    server.read_errors[DEVICE_B] = BabyTrackerConnectionError("down")
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.helpers.storage.Store.async_save",
        side_effect=OSError("disk full"),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "disk full" in caplog.text


async def test_a_rejected_login_is_reported_with_a_translation_key(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, server: FakeServer
) -> None:
    """Test a rejected login fails setup with a translated reason."""
    server.password = "other-password"
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "auth_failed"
