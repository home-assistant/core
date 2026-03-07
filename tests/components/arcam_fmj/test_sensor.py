"""Tests for Arcam FMJ sensor entities."""

from unittest.mock import Mock

import pytest

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
    """Test that sensor entities are created for both zones, disabled by default."""
    for zone in (1, 2):
        for key in SENSOR_KEYS:
            entity_id = _get_entity_id(entity_registry, zone, key)
            entry = entity_registry.async_get(entity_id)
            assert entry is not None
            assert entry.disabled_by is not None


@pytest.mark.usefixtures("player_setup")
async def test_sensor_video_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test sensor values for incoming video parameters."""
    video_params = Mock()
    video_params.horizontal_resolution = 1920
    video_params.vertical_resolution = 1080
    video_params.refresh_rate = 60
    video_params.aspect_ratio = Mock()
    video_params.aspect_ratio.name = "ASPECT_16_9"
    video_params.colorspace = Mock()
    video_params.colorspace.name = "RGB"
    state_1.get_incoming_video_parameters.return_value = video_params

    expected = {
        "incoming_video_horizontal_resolution": "1920",
        "incoming_video_vertical_resolution": "1080",
        "incoming_video_refresh_rate": "60",
        "incoming_video_aspect_ratio": "ASPECT_16_9",
        "incoming_video_colorspace": "RGB",
    }

    # Enable sensors
    for key in expected:
        entity_id = _get_entity_id(entity_registry, 1, key)
        entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    for key, expected_value in expected.items():
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == expected_value, (
            f"Wrong value for {key}: {state.state} != {expected_value}"
        )


@pytest.mark.usefixtures("player_setup")
async def test_sensor_audio_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test sensor values for incoming audio parameters."""
    audio_format = Mock()
    audio_format.name = "DOLBY_DIGITAL"
    audio_config = Mock()
    audio_config.name = "MONO"
    state_1.get_incoming_audio_format.return_value = (audio_format, audio_config)
    state_1.get_incoming_audio_sample_rate.return_value = 48000

    expected = {
        "incoming_audio_format": "DOLBY_DIGITAL",
        "incoming_audio_config": "MONO",
        "incoming_audio_sample_rate": "48000",
    }

    for key in expected:
        entity_id = _get_entity_id(entity_registry, 1, key)
        entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    for key, expected_value in expected.items():
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == expected_value, (
            f"Wrong value for {key}: {state.state} != {expected_value}"
        )


@pytest.mark.usefixtures("player_setup")
async def test_sensor_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
) -> None:
    """Test that sensors handle None video parameters."""
    state_1.get_incoming_video_parameters.return_value = None

    key = "incoming_video_horizontal_resolution"
    entity_id = _get_entity_id(entity_registry, 1, key)
    entity_registry.async_update_entity(entity_id, disabled_by=None)

    config_entry = hass.config_entries.async_entries("arcam_fmj")[0]
    await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
