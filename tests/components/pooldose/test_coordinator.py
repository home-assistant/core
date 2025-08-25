"""Test the PoolDose coordinator."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import RequestStatus

from tests.common import MockConfigEntry, async_load_fixture


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_coordinator_integration_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator is properly set up through integration."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify coordinator exists in runtime_data
    assert mock_config_entry.runtime_data is not None
    assert hasattr(mock_config_entry.runtime_data, "coordinator")
    assert hasattr(mock_config_entry.runtime_data, "client")

    coordinator = mock_config_entry.runtime_data.coordinator
    assert coordinator.last_update_success is True
    assert coordinator.data is not None


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_coordinator_data_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator data has expected structure from fixtures."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator
    data = coordinator.data

    # Verify data structure matches fixture
    assert isinstance(data, dict)
    assert "sensor" in data
    assert "binary_sensor" in data
    assert "number" in data
    assert "switch" in data

    # Check specific sensor data
    assert "temperature" in data["sensor"]
    assert data["sensor"]["temperature"]["value"] == 25
    assert data["sensor"]["temperature"]["unit"] == "°C"


async def test_coordinator_update_failure_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client,
) -> None:
    """Test coordinator handles update failures gracefully."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    # Simulate connection failure
    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.HOST_UNREACHABLE,
        None,
    )

    # Trigger coordinator refresh
    await coordinator.async_refresh()

    # Coordinator should handle the failure gracefully
    assert coordinator.last_update_success is False


async def test_coordinator_data_refresh(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client,
) -> None:
    """Test coordinator data refreshes properly."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    # Initial state
    assert coordinator.data["sensor"]["temperature"]["value"] == 25

    # Update mock data
    new_data = json.loads(await async_load_fixture(hass, "instantvalues.json", DOMAIN))
    new_data["sensor"]["temperature"]["value"] = 30
    mock_pooldose_client.instant_values_structured.return_value = (
        RequestStatus.SUCCESS,
        new_data,
    )

    # Trigger refresh
    await coordinator.async_refresh()

    # Verify data updated
    assert coordinator.data["sensor"]["temperature"]["value"] == 30


@pytest.mark.parametrize(
    "error_status",
    [
        RequestStatus.API_VERSION_UNSUPPORTED,
        RequestStatus.NO_DATA,
        RequestStatus.UNKNOWN_ERROR,
    ],
)
async def test_coordinator_handles_various_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pooldose_client,
    error_status: str,
) -> None:
    """Test coordinator handles various API error statuses."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    coordinator = mock_config_entry.runtime_data.coordinator

    # Simulate API error
    mock_pooldose_client.instant_values_structured.return_value = (
        error_status,
        None,
    )

    await coordinator.async_refresh()

    # Should fail gracefully
    assert coordinator.last_update_success is False


async def test_coordinator_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles timeout errors during data fetch."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True
        mock_client.instant_values_structured = AsyncMock(
            side_effect=TimeoutError("Request timeout")
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_connection_error_during_fetch(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection errors during data fetch."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True
        mock_client.instant_values_structured = AsyncMock(
            side_effect=OSError("Network unreachable")
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_none_data_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles None data from API."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True
        mock_client.instant_values_structured = AsyncMock(
            return_value=(RequestStatus.SUCCESS, None)
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_coordinator_setup_called(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator _async_setup is called and device_info is set."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True

        instant_values_raw = await async_load_fixture(
            hass, "instantvalues.json", DOMAIN
        )
        instant_values_data = json.loads(instant_values_raw)
        mock_client.instant_values_structured = AsyncMock(
            return_value=(RequestStatus.SUCCESS, instant_values_data)
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.LOADED

        # Check that coordinator setup was called and device_info is set
        coordinator = mock_config_entry.runtime_data.coordinator
        assert coordinator.device_info == device_info
