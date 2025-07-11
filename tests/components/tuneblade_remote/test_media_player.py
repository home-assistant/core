"""Tests for the TuneBlade Remote media player platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.media_player import (
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.components.tuneblade_remote.media_player import (
    TuneBladeHubMediaPlayer,
    TuneBladeMediaPlayer,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator


@pytest.fixture
def mock_coordinator() -> AsyncMock:
    """Return a mock DataUpdateCoordinator with dummy TuneBlade device data."""
    coordinator = AsyncMock(spec=DataUpdateCoordinator)
    coordinator.data = {
        "MASTER": {
            "name": "TuneBlade Hub",
            "status_code": "100",
            "volume": 65,
        },
        "abc123": {
            "name": "Living Room",
            "status_code": "200",
            "volume": 45,
        },
    }
    coordinator.client = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_hub_properties(hass: HomeAssistant, mock_coordinator: AsyncMock) -> None:
    """Test properties and state mapping of the master hub entity."""
    entity = TuneBladeHubMediaPlayer(mock_coordinator)
    await entity.async_added_to_hass(hass)
    entity._handle_coordinator_update()

    assert entity.name == "Master"
    assert entity.available
    assert entity.state == MediaPlayerState.PLAYING
    assert entity.volume_level == 0.65
    assert entity.supported_features == (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
    )
    assert entity.extra_state_attributes["status_text"] == "playing"
    assert entity.device_info["identifiers"] == {(DOMAIN, "MASTER")}


@pytest.mark.asyncio
async def test_device_properties(
    hass: HomeAssistant, mock_coordinator: AsyncMock
) -> None:
    """Test properties and state mapping of a normal device entity."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, "abc123", mock_coordinator.data["abc123"]
    )
    await entity.async_added_to_hass(hass)
    entity._handle_coordinator_update()

    assert entity.name == "Living Room"
    assert entity.available
    assert entity.state == MediaPlayerState.IDLE
    assert entity.volume_level == 0.45
    assert entity.extra_state_attributes["status_text"] == "standby"
    assert entity.device_info["identifiers"] == {(DOMAIN, "abc123")}
    assert entity.device_info["via_device"] == (DOMAIN, "MASTER")


@pytest.mark.asyncio
async def test_hub_control_methods(mock_coordinator: AsyncMock) -> None:
    """Test the turn_on, turn_off, and volume methods of the hub media player."""
    entity = TuneBladeHubMediaPlayer(mock_coordinator)

    await entity.async_turn_on()
    mock_coordinator.client.connect.assert_called_once_with("MASTER")

    await entity.async_turn_off()
    mock_coordinator.client.disconnect.assert_called_once_with("MASTER")

    await entity.async_set_volume_level(0.55)
    mock_coordinator.client.set_volume.assert_called_once_with("MASTER", 55)


@pytest.mark.asyncio
async def test_device_control_methods(mock_coordinator: AsyncMock) -> None:
    """Test the turn_on, turn_off, and volume methods of a normal media player device."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, "abc123", mock_coordinator.data["abc123"]
    )

    await entity.async_turn_on()
    mock_coordinator.client.connect.assert_called_once_with("abc123")

    await entity.async_turn_off()
    mock_coordinator.client.disconnect.assert_called_once_with("abc123")

    await entity.async_set_volume_level(0.8)
    mock_coordinator.client.set_volume.assert_called_once_with("abc123", 80)
