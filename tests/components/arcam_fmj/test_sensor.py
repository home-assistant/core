"""Tests for Arcam FMJ sensor entities."""

import pytest

from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_UUID

SENSOR_KEYS = [
    "incoming_video_horizontal_resolution",
    "incoming_video_vertical_resolution",
    "incoming_video_refresh_rate",
    "incoming_video_aspect_ratio",
    "incoming_video_colorspace",
    "incoming_audio_format",
    "incoming_audio_config",
    "incoming_audio_sample_rate",
]


def _get_entity_id(entity_registry: er.EntityRegistry, zone: int, key: str) -> str:
    """Get entity_id by unique_id."""
    unique_id = f"{MOCK_UUID}-{zone}-{key}"
    entity_id = entity_registry.async_get_entity_id("sensor", "arcam_fmj", unique_id)
    assert entity_id is not None, f"Missing sensor: zone {zone} {key}"
    return entity_id


@pytest.mark.usefixtures("player_setup")
async def test_sensors_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensor entities are created for both zones."""
    for zone in (1, 2):
        for key in SENSOR_KEYS:
            entity_id = _get_entity_id(entity_registry, zone, key)
            entry = entity_registry.async_get(entity_id)
            assert entry is not None


@pytest.mark.usefixtures("player_setup")
async def test_sensor_video_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors report unknown when video parameters are None."""
    for key in SENSOR_KEYS[:5]:
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == STATE_UNKNOWN, f"Expected unknown for {key}"


@pytest.mark.usefixtures("player_setup")
async def test_sensor_audio_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensors report unknown when audio format is None."""
    for key in ("incoming_audio_format", "incoming_audio_config"):
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == STATE_UNKNOWN, f"Expected unknown for {key}"
