"""Test Tewke coordinator exceptions."""

import logging
from unittest.mock import AsyncMock, patch

import pytest
from pytewke.data import ConfigData
from pytewke.error import PyTewkeCoapError

from homeassistant.components.tewke.coordinator import TewkeCoordinator, UpdateFailed
from homeassistant.components.tewke.data import TewkeData
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_tap")


async def test_coordinator_setup_observe_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when _setup_observe raises an exception."""
    mock_tap.get_scenes = AsyncMock(return_value={})
    mock_tap.get_targets = AsyncMock(return_value=[])
    mock_tap.get_sensors = AsyncMock(return_value=None)
    mock_tap.get_radar = AsyncMock(return_value=None)
    mock_tap.get_energy = AsyncMock(return_value=None)
    mock_tap.get_energy_override = AsyncMock(return_value=None)
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData.model_construct(
            hardware_id="test_dock_id",
        )
    )

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
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


async def test_coordinator_device_swap(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test device swap detection."""
    mock_tap.wall_dock_id = "different_dock_id"
    mock_tap.get_scenes = AsyncMock()

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with (
        patch.object(coordinator, "_setup_observe", return_value=True),
        pytest.raises(UpdateFailed, match="device_swap"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_get_scenes_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when get_scenes fails with a CoAP error."""
    mock_tap.get_scenes = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with (
        patch("homeassistant.components.tewke.coordinator.asyncio.sleep"),
        patch.object(coordinator, "_setup_observe", return_value=True),
        pytest.raises(UpdateFailed, match="communication_error"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_get_targets_fails(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when get_targets fails with a TimeoutError."""
    mock_tap.get_scenes = AsyncMock(return_value={})
    mock_tap.get_targets = AsyncMock(side_effect=TimeoutError())
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
        observe_active=False,
    )

    coordinator = TewkeCoordinator(
        hass, logging.getLogger(__name__), "Tewke Tap", mock_config_entry
    )
    with (
        patch("homeassistant.components.tewke.coordinator.asyncio.sleep"),
        patch.object(coordinator, "_setup_observe", return_value=True),
        pytest.raises(UpdateFailed, match="communication_error"),
    ):
        await coordinator._async_update_data()


async def test_coordinator_optional_endpoints_fail(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_tap: AsyncMock
) -> None:
    """Test when optional endpoints fail with a CoAP error."""
    mock_tap.get_scenes = AsyncMock(return_value={})
    mock_tap.get_targets = AsyncMock(return_value=[])
    mock_tap.get_sensors = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_radar = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_energy = AsyncMock(side_effect=PyTewkeCoapError("Timeout", 408))
    mock_tap.get_energy_override = AsyncMock(
        side_effect=PyTewkeCoapError("Timeout", 408)
    )
    mock_tap.get_config = AsyncMock(
        return_value=ConfigData.model_construct(  # type: ignore[call-arg]
            hardware_id="test_dock_id",
        )
    )
    mock_tap.wall_dock_id = "test_dock_id"

    mock_config_entry.runtime_data = TewkeData(
        host="127.0.0.1",
        tap=mock_tap,
        coordinator=AsyncMock(),
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
        assert data["config"].hardware_id == "test_dock_id"
