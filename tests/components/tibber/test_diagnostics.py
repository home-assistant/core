"""Test the Tibber diagnostics."""

from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
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


async def test_entry_diagnostics_empty(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_tibber_setup: MagicMock,
) -> None:
    """Test config entry diagnostics with no homes."""
    tibber_mock = mock_tibber_setup
    tibber_mock.get_homes.return_value = []

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(result, dict)
    assert "homes" in result
    assert "devices" in result
    assert result["homes"] == []
    assert result["devices"] == []


async def test_entry_diagnostics_with_homes(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    mock_tibber_setup: MagicMock,
) -> None:
    """Test config entry diagnostics with homes."""
    tibber_mock = mock_tibber_setup
    tibber_mock.get_homes.side_effect = mock_get_homes

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert isinstance(result, dict)
    assert "homes" in result
    assert "devices" in result

    homes = result["homes"]
    assert isinstance(homes, list)
    assert len(homes) == 1

    home = homes[0]
    assert "last_data_timestamp" in home
    assert "has_active_subscription" in home
    assert "has_real_time_consumption" in home
    assert "last_cons_data_timestamp" in home
    assert "country" in home
    assert home["has_active_subscription"] is True
    assert home["has_real_time_consumption"] is False
    assert home["country"] == "NO"


async def test_data_api_diagnostics_no_data(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: MagicMock,
    setup_credentials: None,
) -> None:
    """Test Data API diagnostics when coordinator has no data."""
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    data_api_client_mock.get_all_devices.assert_awaited_once()
    data_api_client_mock.update_devices.assert_awaited_once()

    result = await async_get_config_entry_diagnostics(hass, config_entry)

    assert isinstance(result, dict)
    assert "homes" in result
    assert "devices" in result
    assert isinstance(result["homes"], list)
    assert isinstance(result["devices"], list)
    assert result["devices"] == []


async def test_data_api_diagnostics_with_devices(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    data_api_client_mock: MagicMock,
    setup_credentials: None,
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

    assert isinstance(result, dict)
    assert "homes" in result
    assert "devices" in result

    devices_list = result["devices"]
    assert isinstance(devices_list, list)
    assert len(devices_list) == 2

    device_1 = next((d for d in devices_list if d["id"] == "device-1"), None)
    assert device_1 is not None
    assert device_1["name"] == "Device 1"
    assert device_1["brand"] == "Tibber"
    assert device_1["model"] == "Test Model"

    device_2 = next((d for d in devices_list if d["id"] == "device-2"), None)
    assert device_2 is not None
    assert device_2["name"] == "Device 2"
    assert device_2["brand"] == "Tibber"
    assert device_2["model"] == "Test Model"


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
