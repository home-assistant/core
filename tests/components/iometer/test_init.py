"""Tests for the IOmeter integration."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

from iometer import (
    IOmeterConnectionError,
    IOmeterNoReadingsError,
    IOmeterNoStatusError,
    IOmeterTimeoutError,
    Reading,
    Status,
)
import pytest

from homeassistant.components.iometer.const import DOMAIN
from homeassistant.components.iometer.coordinator import IOMeterCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import setup_platform

from tests.common import MockConfigEntry, async_load_fixture


async def test_new_firmware_version(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    status_queue: asyncio.Queue[Status],
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
    status_queue.put_nowait(Status.from_json(json.dumps(status_data)))
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry.sw_version == "build-62/build-69"


async def test_async_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup retries when initial SSE data never arrives."""
    mock_config_entry.add_to_hass(hass)
    with patch.object(
        IOMeterCoordinator,
        "_async_update_data",
        side_effect=UpdateFailed("Timeout waiting for IOmeter data"),
    ):
        result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert not result
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


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
    "exception",
    [
        pytest.param(IOmeterTimeoutError("timeout"), id="timeout"),
        pytest.param(IOmeterNoReadingsError("no readings"), id="no-readings"),
        pytest.param(IOmeterConnectionError("connection error"), id="connection-error"),
        pytest.param(RuntimeError("unexpected"), id="unexpected"),
    ],
)
async def test_reading_stream_reconnects(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    reading_queue: asyncio.Queue[Reading],
    exception: Exception,
) -> None:
    """Test reading stream reconnects after error."""
    call_count = 0

    async def watch_readings_with_error():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise exception
        yield await reading_queue.get()

    mock_iometer_client.watch_readings.side_effect = watch_readings_with_error

    with patch("homeassistant.components.iometer.coordinator.asyncio.sleep"):
        await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    assert call_count >= 2


@pytest.mark.parametrize(
    "exception",
    [
        pytest.param(IOmeterTimeoutError("timeout"), id="timeout"),
        pytest.param(IOmeterNoStatusError("no status"), id="no-status"),
        pytest.param(IOmeterConnectionError("connection error"), id="connection-error"),
        pytest.param(RuntimeError("unexpected"), id="unexpected"),
    ],
)
async def test_status_stream_reconnects(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    status_queue: asyncio.Queue[Status],
    exception: Exception,
) -> None:
    """Test status stream reconnects after error."""
    call_count = 0

    async def watch_status_with_error():
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise exception
        yield await status_queue.get()

    mock_iometer_client.watch_status.side_effect = watch_status_with_error

    with patch("homeassistant.components.iometer.coordinator.asyncio.sleep"):
        await setup_platform(hass, mock_config_entry, [Platform.SENSOR])

    assert call_count >= 2
