"""Tests for the IOmeter integration."""

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
from homeassistant.helpers.update_coordinator import UpdateFailed

from . import get_status_callback, setup_platform

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
    coordinator = mock_config_entry.runtime_data

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.iometer"):
        coordinator._on_reading_error(exception)

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
    coordinator = mock_config_entry.runtime_data

    with caplog.at_level(logging.DEBUG, logger="homeassistant.components.iometer"):
        coordinator._on_status_error(exception)

    assert expected_log in caplog.text


async def test_error_before_first_data_does_not_mark_unavailable(
    hass: HomeAssistant,
    mock_iometer_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that stream errors before first data do not mark entities unavailable."""
    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    coordinator = mock_config_entry.runtime_data

    coordinator._first_data_event.clear()
    coordinator.last_update_success = True

    coordinator._on_reading_error(IOmeterConnectionError("err"))

    assert coordinator.last_update_success is True
