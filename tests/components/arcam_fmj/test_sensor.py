"""Tests for Arcam FMJ sensor entities."""

from unittest.mock import Mock

import pytest

from homeassistant.components.arcam_fmj.coordinator import ArcamFmjCoordinator
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_video_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test sensor values for incoming video parameters."""
    video_params = Mock()
    video_params.horizontal_resolution = 1920
    video_params.vertical_resolution = 1080
    video_params.refresh_rate = 60
    video_params.aspect_ratio = Mock()
    video_params.aspect_ratio.name = "ASPECT_16_9"
    video_params.colorspace = Mock()
    video_params.colorspace.name = "HDR10"
    state_1.get_incoming_video_parameters.return_value = video_params

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    expected = {
        "incoming_video_horizontal_resolution": "1920",
        "incoming_video_vertical_resolution": "1080",
        "incoming_video_refresh_rate": "60",
        "incoming_video_aspect_ratio": "aspect_16_9",
        "incoming_video_colorspace": "hdr10",
    }

    for key, expected_value in expected.items():
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == expected_value, (
            f"Wrong value for {key}: {state.state} != {expected_value}"
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_audio_parameters(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test sensor values for incoming audio parameters."""
    audio_format = Mock()
    audio_format.name = "DOLBY_DIGITAL"
    audio_config = Mock()
    audio_config.name = "MONO"
    state_1.get_incoming_audio_format.return_value = (audio_format, audio_config)
    state_1.get_incoming_audio_sample_rate.return_value = 48000

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    expected = {
        "incoming_audio_format": "dolby_digital",
        "incoming_audio_config": "mono",
        "incoming_audio_sample_rate": "48000",
    }

    for key, expected_value in expected.items():
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == expected_value, (
            f"Wrong value for {key}: {state.state} != {expected_value}"
        )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_video_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test that sensors handle None video parameters."""
    state_1.get_incoming_video_parameters.return_value = None

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(
        entity_registry, 1, "incoming_video_horizontal_resolution"
    )
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_audio_none_values(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test that sensors handle None audio format."""
    state_1.get_incoming_audio_format.return_value = (None, None)

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    for key in ("incoming_audio_format", "incoming_audio_config"):
        entity_id = _get_entity_id(entity_registry, 1, key)
        state = hass.states.get(entity_id)
        assert state is not None, f"State missing for {key}"
        assert state.state == STATE_UNKNOWN, f"Expected unknown for {key}"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_signal_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test sensor updates on data signal."""
    state_1.get_incoming_audio_sample_rate.return_value = 44100

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    key = "incoming_audio_sample_rate"
    entity_id = _get_entity_id(entity_registry, 1, key)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "44100"

    # Change value and notify coordinator
    state_1.get_incoming_audio_sample_rate.return_value = 96000
    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "96000"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_signal_stopped(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test sensor becomes unavailable on stopped signal."""
    state_1.get_incoming_audio_sample_rate.return_value = 48000

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    key = "incoming_audio_sample_rate"
    entity_id = _get_entity_id(entity_registry, 1, key)

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "48000"

    coordinator_1.async_notify_disconnected()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_signal_started(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    state_1: Mock,
    coordinator_1: ArcamFmjCoordinator,
) -> None:
    """Test sensor becomes available on started signal."""
    state_1.get_incoming_audio_sample_rate.return_value = 48000

    coordinator_1.async_set_updated_data(state_1)
    await hass.async_block_till_done()

    key = "incoming_audio_sample_rate"
    entity_id = _get_entity_id(entity_registry, 1, key)

    # First make it unavailable
    coordinator_1.async_notify_disconnected()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    # Then bring it back
    coordinator_1.async_notify_connected()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "48000"
