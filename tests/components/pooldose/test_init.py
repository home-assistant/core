"""Test the PoolDose integration initialization."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .conftest import RequestStatus

from tests.common import MockConfigEntry, async_load_fixture


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Verify runtime data was set
    assert mock_config_entry.runtime_data is not None
    assert hasattr(mock_config_entry.runtime_data, "client")
    assert hasattr(mock_config_entry.runtime_data, "coordinator")


async def test_setup_entry_connection_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when client connection fails."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
        mock_client.is_connected = False

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_coordinator_refresh_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when coordinator first refresh fails."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True
        # Make instant_values_structured fail
        mock_client.instant_values_structured = AsyncMock(
            side_effect=Exception("API communication failed")
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_unload_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test successful unloading of config entry."""
    mock_config_entry.add_to_hass(hass)

    # First set up the entry
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Now test unloading
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_pooldose_client")
async def test_reload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reloading the config entry."""
    mock_config_entry.add_to_hass(hass)

    # Setup
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED

    # Reload
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "status",
    [
        RequestStatus.HOST_UNREACHABLE,
        RequestStatus.PARAMS_FETCH_FAILED,
        RequestStatus.API_VERSION_UNSUPPORTED,
        RequestStatus.NO_DATA,
        RequestStatus.UNKNOWN_ERROR,
    ],
)
async def test_setup_entry_various_client_failures(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    status,
) -> None:
    """Test setup fails with various client error statuses."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(return_value=status)
        mock_client.is_connected = False

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_platforms_configuration() -> None:
    """Test that PLATFORMS is correctly configured."""
    from homeassistant.components.pooldose import PLATFORMS  # noqa: PLC0415

    assert PLATFORMS == [Platform.SENSOR]
    assert len(PLATFORMS) == 1
    assert Platform.SENSOR in PLATFORMS


async def test_setup_entry_timeout_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when client connection times out."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(side_effect=TimeoutError("Connection timeout"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setup failure when client connection has OSError."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        mock_client.connect = AsyncMock(side_effect=OSError("Network error"))

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_runtime_data_structure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that runtime data has correct structure."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.pooldose.PooldoseClient") as mock_client_class:
        mock_client = mock_client_class.return_value
        device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
        device_info = json.loads(device_info_raw)
        mock_client.device_info = device_info
        mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
        mock_client.is_connected = True

        # Mock coordinator first refresh
        with patch(
            "homeassistant.components.pooldose.coordinator.PooldoseCoordinator.async_config_entry_first_refresh"
        ):
            await hass.config_entries.async_setup(mock_config_entry.entry_id)
            await hass.async_block_till_done()

            assert mock_config_entry.state == ConfigEntryState.LOADED

            # Check runtime data structure
            runtime_data = mock_config_entry.runtime_data
            assert runtime_data is not None
            assert hasattr(runtime_data, "client")
            assert hasattr(runtime_data, "coordinator")
            assert hasattr(runtime_data, "device_properties")
            assert runtime_data.client == mock_client
            assert runtime_data.device_properties == device_info
