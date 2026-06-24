"""Tests for the IOmeter integration."""

import asyncio
import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from iometer import (
    IOmeterConnectionError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
    IOmeterTimeoutError,
    Status,
)
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.components.iometer.coordinator import IOMeterCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import (
    get_reading_error_callback,
    get_status_callback,
    get_status_error_callback,
    setup_platform,
)

from tests.common import MockConfigEntry, async_load_fixture


async def test_new_firmware_version(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test device registry is updated when firmware version changes via SSE."""
    assert mock_config_entry.unique_id is not None

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "build-58/build-65"

    status_data = json.loads(await async_load_fixture(hass, "status.json", DOMAIN))
    status_data["device"]["core"]["version"] = "build-62"
    status_data["device"]["bridge"]["version"] = "build-69"
    get_status_callback(mock_iometer_client)(Status.from_json(json.dumps(status_data)))
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "build-62/build-69"


async def test_first_data_timeout(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when the 30s timeout waiting for first SSE data expires."""
    mock_config_entry.add_to_hass(hass)

    mock_timeout = MagicMock()
    mock_timeout.return_value.__aenter__ = AsyncMock(side_effect=TimeoutError)
    mock_timeout.return_value.__aexit__ = AsyncMock(return_value=False)

    with patch(
        "homeassistant.components.iometer.coordinator.asyncio.timeout",
        mock_timeout,
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert not result
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("exception", "expected_log"),
    [
        pytest.param(IOmeterTimeoutError("t"), "timed out", id="timeout"),
        pytest.param(IOmeterNoReadingsError("n"), "stream error", id="no-readings"),
        pytest.param(
            IOmeterConnectionError("c"), "stream error", id="connection-error"
        ),
        pytest.param(
            RuntimeError("u"), "Unexpected error in reading stream", id="unexpected"
        ),
    ],
)
async def test_reading_error_callback(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test reading error callback logs correctly before the library reconnects."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.iometer"):
        get_reading_error_callback(mock_iometer_client)(exception)

    assert expected_log in caplog.text


@pytest.mark.parametrize(
    ("exception", "expected_log"),
    [
        pytest.param(IOmeterTimeoutError("t"), "timed out", id="timeout"),
        pytest.param(IOmeterNoStatusError("n"), "stream error", id="no-status"),
        pytest.param(
            IOmeterConnectionError("c"), "stream error", id="connection-error"
        ),
        pytest.param(
            RuntimeError("u"), "Unexpected error in status stream", id="unexpected"
        ),
    ],
)
async def test_status_error_callback(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_log: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test status error callback logs correctly before the library reconnects."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.iometer"):
        get_status_error_callback(mock_iometer_client)(exception)

    assert expected_log in caplog.text


async def test_error_before_first_data_does_not_mark_unavailable(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that stream errors before first data do not mark entities unavailable."""
    mock_iometer_client.subscribe_readings.side_effect = lambda *_: lambda: None
    mock_iometer_client.subscribe_status.side_effect = lambda *_: lambda: None

    coordinator = IOMeterCoordinator(hass, mock_config_entry, mock_iometer_client)
    await coordinator.async_start()

    with caplog.at_level(logging.WARNING, logger="homeassistant.components.iometer"):
        get_reading_error_callback(mock_iometer_client)(IOmeterConnectionError("err"))

    assert "stream error" in caplog.text
    assert "Update failed" not in caplog.text


@pytest.mark.usefixtures("mock_iometer_client")
async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that unloading an entry succeeds and cleans up the coordinator."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)


async def test_async_stop_awaits_pending_tasks(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test async_stop awaits and cancels SSE tasks that have not yet finished."""
    loop = asyncio.get_running_loop()
    readings_task = loop.create_task(asyncio.Event().wait(), name="readings-task")
    status_task = loop.create_task(asyncio.Event().wait(), name="status-task")

    original_readings = mock_iometer_client.subscribe_readings.side_effect
    original_status = mock_iometer_client.subscribe_status.side_effect

    def subscribe_readings_with_task(*args):
        original_readings(*args)
        return readings_task.cancel

    def subscribe_status_with_task(*args):
        original_status(*args)
        return status_task.cancel

    mock_iometer_client.subscribe_readings.side_effect = subscribe_readings_with_task
    mock_iometer_client.subscribe_status.side_effect = subscribe_status_with_task

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert readings_task.cancelled()
    assert status_task.cancelled()
