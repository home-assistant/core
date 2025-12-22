"""Test the Tibber diagnostics."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from syrupy.assertion import SnapshotAssertion
import tibber

from homeassistant.components.recorder import Recorder
from homeassistant.components.tibber.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed

from .conftest import create_tibber_device
from .test_common import mock_get_homes

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_tibber_setup: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    tibber_mock = mock_tibber_setup
    tibber_mock.get_homes.return_value = []

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot(name="empty")

    tibber_mock.get_homes.side_effect = mock_get_homes

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
    assert result == snapshot(name="with_homes")


async def test_data_api_diagnostics_no_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: MagicMock,
    setup_credentials: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Data API diagnostics when coordinator has no data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data_api_client_mock.get_all_devices.assert_awaited_once()
    data_api_client_mock.update_devices.assert_awaited_once()

    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result == snapshot


async def test_data_api_diagnostics_with_devices(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: MagicMock,
    setup_credentials: None,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Data API diagnostics with successful device retrieval."""
    devices = {
        "device-1": create_tibber_device(
            device_id="device-1",
            name="Device 1",
            brand="Tibber",
            model="Test Model",
        ),
        "device-2": create_tibber_device(
            device_id="device-2",
            name="Device 2",
            brand="Tibber",
            model="Test Model",
        ),
    }

    data_api_client_mock.get_all_devices = AsyncMock(return_value=devices)
    data_api_client_mock.update_devices = AsyncMock(return_value=devices)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await async_get_config_entry_diagnostics(hass, config_entry)
    assert result == snapshot


@pytest.mark.parametrize(
    "exception",
    [
        ConfigEntryAuthFailed("Auth failed"),
        TimeoutError(),
        aiohttp.ClientError("Connection error"),
        tibber.InvalidLoginError(401),
        tibber.RetryableHttpExceptionError(503),
        tibber.FatalHttpExceptionError(404),
    ],
)
async def test_data_api_diagnostics_exceptions(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    tibber_mock: MagicMock,
    setup_credentials: None,
    exception: Exception,
) -> None:
    """Test Data API diagnostics with various exception scenarios."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    tibber_mock.get_homes.side_effect = exception

    with pytest.raises(type(exception)):
        await async_get_config_entry_diagnostics(hass, config_entry)
