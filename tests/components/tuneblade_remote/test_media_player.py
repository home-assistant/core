"""Tests for the TuneBlade media player entity."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.media_player import MediaPlayerState
from homeassistant.components.tuneblade_remote.const import DOMAIN
from homeassistant.components.tuneblade_remote.media_player import (
    MASTER_ID,
    TuneBladeMediaPlayer,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_coordinator() -> AsyncMock:
    """Return a mock coordinator for TuneBlade media player entities."""
    coordinator = AsyncMock()
    # Sample data simulating device info keyed by device ID
    coordinator.data = {
        MASTER_ID: {"name": "Master", "status_code": "100", "volume": 70},
        "abc123": {"name": "Living Room", "status_code": "standby", "volume": 45},
    }
    coordinator.client = AsyncMock()
    return coordinator


@pytest.mark.asyncio
async def test_hub_properties(hass: HomeAssistant, mock_coordinator: AsyncMock) -> None:
    """Test properties and state mapping of the master hub entity."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, MASTER_ID, mock_coordinator.data[MASTER_ID]
    )
    entity.hass = hass
    entity.entity_id = "media_player.master"
    entity._handle_coordinator_update()

    assert entity.name == "Master"  # Matches mock_coordinator data
    assert entity.available
    assert entity.state in (
        MediaPlayerState.IDLE,
        MediaPlayerState.OFF,
        MediaPlayerState.PLAYING,
    )
    assert abs(entity.volume_level - 0.7) < 0.01
    assert entity.device_info["identifiers"] == {(DOMAIN, MASTER_ID)}


@pytest.mark.asyncio
async def test_device_properties(
    hass: HomeAssistant, mock_coordinator: AsyncMock
) -> None:
    """Test properties and state mapping of a normal device entity."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, "abc123", mock_coordinator.data["abc123"]
    )
    entity.hass = hass
    entity.entity_id = "media_player.living_room"
    entity._handle_coordinator_update()

    assert entity.name == "Living Room"
    assert entity.available
    assert entity.state in (MediaPlayerState.OFF, MediaPlayerState.IDLE)
    assert abs(entity.volume_level - 0.45) < 0.01
    assert entity.extra_state_attributes.get("status_text") in ("standby", "unknown")
    assert entity.device_info["identifiers"] == {(DOMAIN, "abc123")}


@pytest.mark.asyncio
async def test_hub_control_methods(mock_coordinator: AsyncMock) -> None:
    """Test control methods of the master hub media player."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, MASTER_ID, mock_coordinator.data[MASTER_ID]
    )
    entity.hass = Mock()

    async def dummy_coro():
        return

    entity.hass.async_create_task = AsyncMock(side_effect=lambda coro: dummy_coro())

    await entity.async_turn_on()
    await entity.async_turn_off()
    await entity.async_set_volume_level(0.5)

    assert entity.hass.async_create_task.call_count >= 1


@pytest.mark.asyncio
async def test_device_control_methods(mock_coordinator: AsyncMock) -> None:
    """Test control methods of a regular media player device."""
    entity = TuneBladeMediaPlayer(
        mock_coordinator, "abc123", mock_coordinator.data["abc123"]
    )
    entity.hass = Mock()

    async def dummy_coro():
        return

    entity.hass.async_create_task = AsyncMock(side_effect=lambda coro: dummy_coro())

    await entity.async_turn_on()
    await entity.async_turn_off()
    await entity.async_set_volume_level(0.5)

    assert entity.hass.async_create_task.call_count >= 1


@pytest.mark.asyncio
async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant, mock_coordinator: AsyncMock
) -> None:
    """Test that async_setup_entry adds all TuneBlade media player entities."""
    config_entry = Mock()
    config_entry.entry_id = "test_entry"
    config_entry.runtime_data = mock_coordinator

    hass.data.setdefault(DOMAIN, {})[config_entry.entry_id] = {"added_ids": set()}

    added_entities = []

    def mock_add_entities(entities, update_before_add=False):
        for entity in entities:
            entity.hass = hass
            entity.entity_id = f"media_player.{entity.device_id.lower()}"
        added_entities.extend(entities)

    await async_setup_entry(hass, config_entry, mock_add_entities)

    assert len(added_entities) == len(mock_coordinator.data)
    assert all(entity.hass is hass for entity in added_entities)
    assert all(
        entity.entity_id.startswith("media_player.") for entity in added_entities
    )
