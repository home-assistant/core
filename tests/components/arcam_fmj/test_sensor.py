"""Tests for Arcam FMJ sensor entities."""

from collections.abc import Generator
from unittest.mock import Mock, patch

from arcam.fmj import IncomingVideoAspectRatio, IncomingVideoColorspace
from arcam.fmj.state import IncomingAudioConfig, IncomingAudioFormat, State
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_UUID

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Limit platform setup to sensor only."""
    with patch("homeassistant.components.arcam_fmj.PLATFORMS", [Platform.SENSOR]):
        yield


def _get_entity_id(entity_registry: er.EntityRegistry, zone: int, key: str) -> str:
    """Get entity_id by unique_id."""
    unique_id = f"{MOCK_UUID}-{zone}-{key}"
    entity_id = entity_registry.async_get_entity_id("sensor", "arcam_fmj", unique_id)
    assert entity_id is not None, f"Missing sensor: zone {zone} {key}"
    return entity_id


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "player_setup")
async def test_setup(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test snapshot of the sensor platform."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


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
