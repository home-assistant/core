"""Test the Pooldose coordinator."""

import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.pooldose.coordinator import PooldoseCoordinator
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_config_entry() -> ConfigEntry:
    """Return a mock config entry."""
    return MagicMock(spec=ConfigEntry)


@pytest.fixture
def mock_client() -> AsyncMock:
    """Return a mock client."""
    return AsyncMock()


@pytest.mark.asyncio
async def test_coordinator_fetches_data(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator fetches data from the API."""
    # Mock successful API response
    mock_client.instant_values.return_value = (
        "SUCCESS",
        {"ph": [7.2, "pH"], "orp": [650, "mV"]},
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.data is not None
    assert coordinator.last_update_success is True
    status, data = coordinator.data
    assert status == "SUCCESS"
    assert data["ph"] == [7.2, "pH"]
    assert data["orp"] == [650, "mV"]
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_api_error(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator handles API errors."""
    mock_client.instant_values.side_effect = Exception("API error")

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    # Coordinator should handle the exception gracefully
    assert coordinator.last_update_success is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_handles_unsuccessful_status(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator handles unsuccessful API status."""
    # Mock API response with error status
    mock_client.instant_values.return_value = ("ERROR", None)

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    # Coordinator should handle unsuccessful status
    assert coordinator.last_update_success is False
    assert coordinator.data is None
    mock_client.instant_values.assert_called_once()


@pytest.mark.asyncio
async def test_coordinator_data_extraction(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator correctly extracts data from InstantValues."""
    # Mock InstantValues object with internal structure
    mock_instant_values = MagicMock()
    mock_instant_values._mapping = {
        "temperature": {"key": "w_1eommf39k", "type": "sensor"},
        "ph": {"key": "w_1ekeigkin", "type": "sensor"},
        "orp": {"key": "w_1eklenb23", "type": "sensor"},
    }
    mock_instant_values._device_data = {
        "PDPR1H1HAW100_FW539187_w_1eommf39k": {
            "current": 29.0,
            "magnitude": ["°C", "CDEG"],
        },
        "PDPR1H1HAW100_FW539187_w_1ekeigkin": {
            "current": 7.6,
            "magnitude": ["pH", "PH"],
        },
        "PDPR1H1HAW100_FW539187_w_1eklenb23": {
            "current": 708,
            "magnitude": ["mV", "MV"],
        },
    }
    mock_instant_values._prefix = "PDPR1H1HAW100_FW539187_"

    mock_client.instant_values.return_value = ("SUCCESS", mock_instant_values)

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    status, data = coordinator.data
    assert status == "SUCCESS"
    assert data["temperature"] == [29.0, "°C"]
    assert data["ph"] == [7.6, "pH"]
    assert data["orp"] == [708, "mV"]


@pytest.mark.asyncio
async def test_coordinator_with_conversion(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator correctly applies conversions."""
    # Mock InstantValues with conversion mapping
    mock_instant_values = MagicMock()
    mock_instant_values._mapping = {
        "ph_type_dosing": {
            "key": "w_1eklg44ro",
            "type": "sensor",
            "conversion": {
                "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ALCALYNE|": "alcalyne",
                "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ACID|": "acid",
            },
        },
    }
    mock_instant_values._device_data = {
        "PDPR1H1HAW100_FW539187_w_1eklg44ro": {
            "current": "|PDPR1H1HAW100_FW539187_LABEL_w_1eklg44ro_ALCALYNE|",
            "magnitude": ["UNDEFINED", "UNDEFINED"],
        },
    }
    mock_instant_values._prefix = "PDPR1H1HAW100_FW539187_"

    mock_client.instant_values.return_value = ("SUCCESS", mock_instant_values)

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    status, data = coordinator.data
    assert status == "SUCCESS"
    assert data["ph_type_dosing"] == ["alcalyne", None]  # Converted value, no unit


@pytest.mark.asyncio
async def test_coordinator_missing_attributes(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test that the coordinator handles missing attributes gracefully."""
    # Mock InstantValues without required attributes
    mock_instant_values = MagicMock()
    del mock_instant_values._mapping  # Remove required attribute
    del mock_instant_values._device_data  # Remove required attribute

    mock_client.instant_values.return_value = ("SUCCESS", mock_instant_values)

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    await coordinator.async_refresh()

    assert coordinator.last_update_success is True
    status, data = coordinator.data
    assert status == "SUCCESS"
    assert data == {}  # Empty data when attributes are missing


@pytest.mark.asyncio
async def test_coordinator_availability_property(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: ConfigEntry,
) -> None:
    """Test the coordinator's availability property."""
    mock_client.instant_values.return_value = (
        "SUCCESS",
        {"ph": [7.2, "pH"]},
    )

    coordinator = PooldoseCoordinator(
        hass,
        mock_client,
        datetime.timedelta(seconds=30),
        mock_config_entry,
    )

    # Initially not available (no data fetched yet)
    assert coordinator.available is False

    await coordinator.async_refresh()

    # Should be available after successful refresh
    assert coordinator.available is True

    # Simulate API failure
    mock_client.instant_values.side_effect = Exception("Connection failed")
    await coordinator.async_refresh()

    # Should not be available after failure
    assert coordinator.available is False
