"""Tests for Arcam FMJ sensor entities."""

from unittest.mock import Mock

from arcam.fmj import IncomingVideoAspectRatio, IncomingVideoColorspace
from arcam.fmj.state import IncomingAudioConfig, IncomingAudioFormat, State
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


@pytest.mark.usefixtures("player_setup")
async def test_sensor_video_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: State,
    client: Mock,
) -> None:
    """Test video parameter sensors with actual data."""
    video_params = Mock()
    video_params.horizontal_resolution = 1920
    video_params.vertical_resolution = 1080
    video_params.refresh_rate = 60.0
    video_params.aspect_ratio = IncomingVideoAspectRatio.ASPECT_16_9
    video_params.colorspace = IncomingVideoColorspace.HDR10

    state_1.get_incoming_video_parameters.return_value = video_params
    client.notify_data_updated()
    await hass.async_block_till_done()

    expected = {
        "incoming_video_horizontal_resolution": "1920",
        "incoming_video_vertical_resolution": "1080",
        "incoming_video_refresh_rate": "60.0",
        "incoming_video_aspect_ratio": "aspect_16_9",
        "incoming_video_colorspace": "hdr10",
    }
    for key, value in expected.items():
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == value, f"Expected {value} for {key}, got {state.state}"


@pytest.mark.usefixtures("player_setup")
async def test_sensor_audio_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: State,
    client: Mock,
) -> None:
    """Test audio parameter sensors with actual data."""
    state_1.get_incoming_audio_format.return_value = (
        IncomingAudioFormat.PCM,
        IncomingAudioConfig.STEREO_ONLY,
    )
    state_1.get_incoming_audio_sample_rate.return_value = 48000

    client.notify_data_updated()
    await hass.async_block_till_done()

    entity_id = _get_entity_id(entity_registry, 1, "incoming_audio_format")
    assert hass.states.get(entity_id).state == "pcm"

    entity_id = _get_entity_id(entity_registry, 1, "incoming_audio_config")
    assert hass.states.get(entity_id).state == "stereo_only"

    entity_id = _get_entity_id(entity_registry, 1, "incoming_audio_sample_rate")
    assert hass.states.get(entity_id).state == "48000"
