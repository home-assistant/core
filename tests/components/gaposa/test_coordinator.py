"""Tests for the Gaposa Data Update Coordinator."""

from datetime import timedelta
import logging
from unittest.mock import AsyncMock, MagicMock, patch

from pygaposa import FirebaseAuthException, GaposaAuthException
import pytest

from homeassistant.components.gaposa.const import UPDATE_INTERVAL, UPDATE_INTERVAL_FAST
from homeassistant.components.gaposa.coordinator import DataUpdateCoordinatorGaposa
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed


@pytest.fixture
def motors():
    """Return a mock for a list of motors."""
    return [MagicMock(id=7), MagicMock(id=8)]


@pytest.fixture
def device(motors):
    """Return a mock for a device."""
    return MagicMock(serial="serial", motors=motors)


@pytest.fixture
def mock_gaposa(device):
    """Return a mock Gaposa client."""
    with patch(
        "homeassistant.components.gaposa.coordinator.Gaposa", autospec=True
    ) as mock:
        mock_client = MagicMock(devices=[device])
        mock.configure_mock(clients=[(mock_client, "user")])
        yield mock


@pytest.fixture
def coordinator(hass: HomeAssistant, mock_gaposa):
    """Return an initialized Gaposa DataUpdateCoordinator."""
    logger = logging.getLogger("test")
    coordinator = DataUpdateCoordinatorGaposa(
        hass,
        logger,
        api_key="test_api_key",
        username="test_username",
        password="test_password",
        name="Test Coordinator",
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )
    # Manually set the gaposa object for testing
    coordinator.gaposa = mock_gaposa
    return coordinator


async def test_update_gateway_success(coordinator, mock_gaposa) -> None:
    """Test successful update_gateway call."""
    mock_gaposa.update = AsyncMock(return_value=True)
    assert await coordinator.update_gateway() is True


async def test_update_gateway_auth_fail(coordinator, mock_gaposa) -> None:
    """Test update_gateway with authentication failure."""
    mock_gaposa.update.side_effect = GaposaAuthException
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.update_gateway()


async def test_update_gateway_firebase_auth_fail(coordinator, mock_gaposa) -> None:
    """Test update_gateway with Firebase authentication failure."""
    mock_gaposa.update.side_effect = FirebaseAuthException
    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator.update_gateway()


async def test_async_update_data(coordinator, mock_gaposa) -> None:
    """Test _async_update_data method."""
    mock_gaposa.update = AsyncMock(return_value=True)
    data = await coordinator._async_update_data()
    assert data is not None
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)


async def test_async_update_data_fast_interval(coordinator, mock_gaposa) -> None:
    """Test _async_update_data method with fast interval."""
    mock_gaposa.update = AsyncMock(side_effect=Exception("Error message"))
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL_FAST)


async def test_on_document_updated(coordinator, mock_gaposa, motors) -> None:
    """Test on_document_updated method."""
    coordinator.async_set_updated_data = MagicMock()
    coordinator.on_document_updated()
    assert coordinator.async_set_updated_data.assert_called_once

    data = coordinator.async_set_updated_data.call_args[0][0]
    assert data is not None
    assert data["serial.motors.7"] == motors[0]
    assert data["serial.motors.8"] == motors[1]


async def test_coordinator_update_with_network_error(coordinator, mock_gaposa) -> None:
    """Test coordinator update with network error."""
    mock_gaposa.update.side_effect = ConnectionError
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_coordinator_refresh_interval(coordinator, mock_gaposa) -> None:
    """Test coordinator refresh interval changes."""
    # Test normal interval
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)

    # Test fast interval after error
    mock_gaposa.update.side_effect = Exception("Test error")
    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL_FAST)

    # Test return to normal interval after successful update
    mock_gaposa.update.side_effect = None
    mock_gaposa.update.return_value = True
    await coordinator._async_update_data()
    assert coordinator.update_interval == timedelta(seconds=UPDATE_INTERVAL)
