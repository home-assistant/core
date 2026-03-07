"""Tests for Arcam FMJ binary sensor entities."""

from unittest.mock import Mock

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_UUID


def _get_entity_id(entity_registry: er.EntityRegistry, zone: int) -> str:
    """Get entity_id for the interlaced binary sensor by unique_id."""
    unique_id = f"{MOCK_UUID}-{zone}-incoming_video_interlaced"
    entity_id = entity_registry.async_get_entity_id(
        "binary_sensor", "arcam_fmj", unique_id
    )
    assert entity_id is not None, f"Missing binary sensor: zone {zone}"
    return entity_id


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensors_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that binary sensor entities are created for both zones."""
    for zone in (1, 2):
        entity_id = _get_entity_id(entity_registry, zone)
        entry = entity_registry.async_get(entity_id)
        assert entry is not None
        assert entry.disabled_by is not None


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_interlaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor value for interlaced video."""
    video_params = Mock()
    video_params.interlaced = True
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "on"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_not_interlaced(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor value for progressive video."""
    video_params = Mock()
    video_params.interlaced = False
    state_1.get_incoming_video_parameters.return_value = video_params

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "off"


@pytest.mark.usefixtures("player_setup")
async def test_binary_sensor_none(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test binary sensor when video parameters are None."""
    state_1.get_incoming_video_parameters.return_value = None

    entity_id = _get_entity_id(entity_registry, 1)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
