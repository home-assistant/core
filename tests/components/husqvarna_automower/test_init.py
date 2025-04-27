"""Tests for init module."""

from asyncio import Event
from datetime import datetime
import http
import time
from unittest.mock import AsyncMock, patch

from aioautomower.exceptions import (
    ApiError,
    AuthError,
    HusqvarnaTimeoutError,
    HusqvarnaWSServerHandshakeError,
)
from aioautomower.model import MowerAttributes, WorkArea
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.husqvarna_automower.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.components.husqvarna_automower.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from . import setup_integration
from .const import TEST_MOWER_ID

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

ADDITIONAL_NUMBER_ENTITIES = 1
ADDITIONAL_SENSOR_ENTITIES = 2
ADDITIONAL_SWITCH_ENTITIES = 1


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test load and unload entry."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("scope"),
    [
        ("iam:read"),
    ],
)
async def test_load_missing_scope(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test if the entry starts a reauth with the missing token scope."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    result = flows[0]
    assert result["step_id"] == "missing_scope"


@pytest.mark.parametrize(
    ("expires_at", "status", "expected_state"),
    [
        (
            time.time() - 3600,
            http.HTTPStatus.UNAUTHORIZED,
            ConfigEntryState.SETUP_ERROR,
        ),
        (
            time.time() - 3600,
            http.HTTPStatus.INTERNAL_SERVER_ERROR,
            ConfigEntryState.SETUP_RETRY,
        ),
    ],
    ids=["unauthorized", "internal_server_error"],
)
async def test_expired_token_refresh_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
    status: http.HTTPStatus,
    expected_state: ConfigEntryState,
) -> None:
    """Test failure while refreshing token with a transient error."""

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        OAUTH2_TOKEN,
        status=status,
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state


@pytest.mark.parametrize(
    ("exception", "entry_state"),
    [
        (ApiError, ConfigEntryState.SETUP_RETRY),
        (AuthError, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_update_failed(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    entry_state: ConfigEntryState,
) -> None:
    """Test update failed."""
    mock_automower_client.get_status.side_effect = exception("Test error")
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.state is entry_state


@patch(
    "homeassistant.components.husqvarna_automower.coordinator.DEFAULT_RECONNECT_TIME", 0
)
@pytest.mark.parametrize(
    ("method_path", "exception", "error_msg"),
    [
        (
            ["auth", "websocket_connect"],
            HusqvarnaWSServerHandshakeError,
            "Failed to connect to websocket.",
        ),
        (
            ["start_listening"],
            HusqvarnaTimeoutError,
            "Failed to listen to websocket.",
        ),
    ],
)
async def test_websocket_not_available(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
    method_path: list[str],
    exception: type[Exception],
    error_msg: str,
) -> None:
    """Test trying to reload the websocket."""
    calls = []
    mock_called = Event()
    mock_stall = Event()

    async def mock_function():
        mock_called.set()
        await mock_stall.wait()
        # Raise the first time the method is awaited
        if not calls:
            calls.append(None)
            raise exception("Boom")
        if mock_side_effect:
            await mock_side_effect()

    # Find the method to mock
    mock = mock_automower_client
    for itm in method_path:
        mock = getattr(mock, itm)
    mock_side_effect = mock.side_effect
    mock.side_effect = mock_function

    # Setup integration and verify log error message
    await setup_integration(hass, mock_config_entry)
    await mock_called.wait()
    mock_called.clear()
    # Allow the exception to be raised
    mock_stall.set()
    assert mock.call_count == 1
    await hass.async_block_till_done()
    assert f"{error_msg} Trying to reconnect: Boom" in caplog.text

    # Simulate a successful connection
    caplog.clear()
    await mock_called.wait()
    mock_called.clear()
    await hass.async_block_till_done()
    assert mock.call_count == 2
    assert "Trying to reconnect: Boom" not in caplog.text

    # Simulate hass shutting down
    await hass.async_stop()
    assert mock.call_count == 2


async def test_device_info(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test select platform."""

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    reg_device = device_registry.async_get_device(
        identifiers={(DOMAIN, TEST_MOWER_ID)},
    )
    assert reg_device == snapshot


async def test_coordinator_automatic_registry_cleanup(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    values: dict[str, MowerAttributes],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test automatic registry cleanup."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    await hass.async_block_till_done()

    # Count current entitties and devices
    current_entites = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    current_devices = len(
        dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    )
    # Remove mower 2 and check if it worked
    mower2 = values.pop("1234")
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (
        len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
        == current_entites - 12
    )
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry.entry_id))
        == current_devices - 1
    )
    # Add mower 2 and check if it worked
    values["1234"] = mower2
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
        == current_entites
    )
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry.entry_id))
        == current_devices
    )

    # Remove mower 1 and check if it worked
    mower1 = values.pop(TEST_MOWER_ID)
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 12
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry.entry_id))
        == current_devices - 1
    )
    # Add mower 1 and check if it worked
    values[TEST_MOWER_ID] = mower1
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert (
        len(dr.async_entries_for_config_entry(device_registry, entry.entry_id))
        == current_devices
    )
    assert (
        len(er.async_entries_for_config_entry(entity_registry, entry.entry_id))
        == current_entites
    )


async def test_add_and_remove_work_area(
    hass: HomeAssistant,
    mock_automower_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    values: dict[str, MowerAttributes],
) -> None:
    """Test adding a work area in runtime."""
    await setup_integration(hass, mock_config_entry)
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    current_entites_start = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    values[TEST_MOWER_ID].work_area_names.append("new work area")
    values[TEST_MOWER_ID].work_area_dict.update({1: "new work area"})
    values[TEST_MOWER_ID].work_areas.update(
        {
            1: WorkArea(
                name="new work area",
                cutting_height=12,
                enabled=True,
                progress=12,
                last_time_completed=datetime(
                    2024, 10, 1, 11, 11, 0, tzinfo=dt_util.get_default_time_zone()
                ),
            )
        }
    )
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    current_entites_after_addition = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    assert (
        current_entites_after_addition
        == current_entites_start
        + ADDITIONAL_NUMBER_ENTITIES
        + ADDITIONAL_SENSOR_ENTITIES
        + ADDITIONAL_SWITCH_ENTITIES
    )

    values[TEST_MOWER_ID].work_area_names.remove("new work area")
    del values[TEST_MOWER_ID].work_area_dict[1]
    del values[TEST_MOWER_ID].work_areas[1]
    values[TEST_MOWER_ID].work_area_names.remove("Front lawn")
    del values[TEST_MOWER_ID].work_area_dict[123456]
    del values[TEST_MOWER_ID].work_areas[123456]
    del values[TEST_MOWER_ID].calendar.tasks[:2]
    values[TEST_MOWER_ID].mower.work_area_id = 654321
    mock_automower_client.get_status.return_value = values
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    current_entites_after_deletion = len(
        er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    )
    assert (
        current_entites_after_deletion
        == current_entites_start
        - ADDITIONAL_SWITCH_ENTITIES
        - ADDITIONAL_NUMBER_ENTITIES
        - ADDITIONAL_SENSOR_ENTITIES
    )
