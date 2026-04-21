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

from tests.common import MockConfigEntry, snapshot_platform


@pytest.fixture(autouse=True)
def sensor_only() -> Generator[None]:
    """Limit platform setup to sensor only."""
    with patch("homeassistant.components.arcam_fmj.PLATFORMS", [Platform.SENSOR]):
        yield


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
        state = hass.states.get(f"sensor.arcam_fmj_127_0_0_1_{key}")
        assert state is not None, f"State missing for {key}"
        assert state.state == value, f"Expected {value} for {key}, got {state.state}"


@pytest.mark.usefixtures("player_setup")
async def test_sensor_audio_parameters(
    hass: HomeAssistant,
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

    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_format").state
        == "pcm"
    )
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_configuration").state
        == "stereo_only"
    )
    assert (
        hass.states.get("sensor.arcam_fmj_127_0_0_1_incoming_audio_sample_rate").state
        == "48000"
    )
