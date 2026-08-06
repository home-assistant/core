import logging
from unittest.mock import AsyncMock, patch

import pytest
from pytewke.error import PyTewkeCoapError

from homeassistant.components.tewke.coordinator import TewkeCoordinator, UpdateFailed
from homeassistant.components.tewke.data import TewkeData

pytestmark = pytest.mark.usefixtures("mock_tap")


async def test_coordinator_setup_observe_fails(hass, mock_config_entry, mock_tap):
    """Test when _setup_observe raises an exception."""
    mock_tap.get_scenes = AsyncMock()
    mock_tap.get_targets = AsyncMock()
    mock_tap.get_sensors = AsyncMock()
    mock_tap.get_radar = AsyncMock()
    mock_tap.get_energy = AsyncMock()
    mock_tap.get_energy_override = AsyncMock()
    mock_tap.get_config = AsyncMock()

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        scenes={},
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with (
        patch.object(
            coordinator, "_setup_observe", side_effect=Exception("Test Exception")
        ),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


async def test_coordinator_device_swap(hass, mock_config_entry, mock_tap):
    """Test device swap detection."""
    mock_tap.wall_dock_id = "different_dock_id"
    mock_tap.get_scenes = AsyncMock()

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        scenes={},
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with patch.object(coordinator, "_setup_observe", return_value=True):
        with pytest.raises(UpdateFailed, match="Device swap detected"):
            await coordinator._async_update_data()


async def test_coordinator_get_scenes_fails(hass, mock_config_entry, mock_tap):
    """Test when get_scenes fails with a CoAP error."""
    mock_tap.get_scenes = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        scenes={},
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with patch.object(coordinator, "_setup_observe", return_value=True):
        with pytest.raises(UpdateFailed, match="Error communicating with Tewke Tap"):
            await coordinator._async_update_data()


async def test_coordinator_get_targets_fails(hass, mock_config_entry, mock_tap):
    """Test when get_targets fails with a TimeoutError."""
    mock_tap.get_scenes = AsyncMock(return_value={})
    mock_tap.get_targets = AsyncMock(side_effect=TimeoutError())
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        scenes={},
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with patch.object(coordinator, "_setup_observe", return_value=True):
        with pytest.raises(UpdateFailed, match="Error communicating with Tewke Tap:"):
            await coordinator._async_update_data()


async def test_coordinator_optional_endpoints_fail(hass, mock_config_entry, mock_tap):
    """Test when optional endpoints fail with a CoAP error."""
    mock_tap.get_scenes = AsyncMock(return_value={})
    mock_tap.get_targets = AsyncMock(return_value=[])
    mock_tap.get_sensors = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_radar = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_energy = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_energy_override = AsyncMock(
        side_effect=PyTewkeCoapError("Timeout", 408)
    )
    mock_tap.get_config = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        scenes={},
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with patch.object(coordinator, "_setup_observe", return_value=True):
        data = await coordinator._async_update_data()
        assert data["sensors"] is None
        assert data["radar"] is None
        assert data["energy"] is None
        assert data["energy_override"] is None
        assert data["config"] is None
