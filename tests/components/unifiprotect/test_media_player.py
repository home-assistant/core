"""Test the UniFi Protect media_player platform."""
# pylint: disable=protected-access
from __future__ import annotations

from copy import copy
from unittest.mock import AsyncMock, Mock

import pytest
from pyunifiprotect.data import Camera
from pyunifiprotect.exceptions import StreamError

from homeassistant.components.media_player.const import (
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
)
from homeassistant.components.unifiprotect.const import DEFAULT_ATTRIBUTION
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    STATE_IDLE,
    STATE_PLAYING,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from .conftest import MockEntityFixture, assert_entity_counts


@pytest.fixture(name="camera")
async def camera_fixture(
    hass: HomeAssistant, mock_entry: MockEntityFixture, mock_camera: Camera
):
    """Fixture for a single camera for testing the media_player platform."""

    # disable pydantic validation so mocking can happen
    Camera.__config__.validate_assignment = False

    camera_obj = mock_camera.copy(deep=True)
    camera_obj._api = mock_entry.api
    camera_obj.channels[0]._api = mock_entry.api
    camera_obj.channels[1]._api = mock_entry.api
    camera_obj.channels[2]._api = mock_entry.api
    camera_obj.name = "Test Camera"
    camera_obj.feature_flags.has_speaker = True

    mock_entry.api.bootstrap.cameras = {
        camera_obj.id: camera_obj,
    }

    await hass.config_entries.async_setup(mock_entry.entry.entry_id)
    await hass.async_block_till_done()

    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    yield (camera_obj, "media_player.test_camera_speaker")

    Camera.__config__.validate_assignment = True


async def test_media_player_setup(
    hass: HomeAssistant,
    camera: tuple[Camera, str],
):
    """Test media_player entity setup."""

    unique_id = f"{camera[0].id}_speaker"
    entity_id = camera[1]

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    expected_volume = float(camera[0].speaker_settings.volume / 100)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_IDLE
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 136708
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == "music"
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == expected_volume


async def test_media_player_update(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[Camera, str],
):
    """Test media_player entity update."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera[0].copy()
    new_camera.talkback_stream = Mock()
    new_camera.talkback_stream.is_running = True

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(camera[1])
    assert state
    assert state.state == STATE_PLAYING


async def test_media_player_set_volume(
    hass: HomeAssistant,
    camera: tuple[Camera, str],
):
    """Test media_player entity test set_volume_level."""

    camera[0].__fields__["set_speaker_volume"] = Mock()
    camera[0].set_speaker_volume = AsyncMock()

    await hass.services.async_call(
        "media_player",
        "volume_set",
        {ATTR_ENTITY_ID: camera[1], "volume_level": 0.5},
        blocking=True,
    )

    camera[0].set_speaker_volume.assert_called_once_with(50)


async def test_media_player_stop(
    hass: HomeAssistant,
    mock_entry: MockEntityFixture,
    camera: tuple[Camera, str],
):
    """Test media_player entity test media_stop."""

    new_bootstrap = copy(mock_entry.api.bootstrap)
    new_camera = camera[0].copy()
    new_camera.talkback_stream = AsyncMock()
    new_camera.talkback_stream.is_running = True

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    new_bootstrap.cameras = {new_camera.id: new_camera}
    mock_entry.api.bootstrap = new_bootstrap
    mock_entry.api.ws_subscription(mock_msg)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {ATTR_ENTITY_ID: camera[1]},
        blocking=True,
    )

    new_camera.talkback_stream.stop.assert_called_once()


async def test_media_player_play(
    hass: HomeAssistant,
    camera: tuple[Camera, str],
):
    """Test media_player entity test play_media."""
    camera[0].__fields__["stop_audio"] = Mock()
    camera[0].__fields__["play_audio"] = Mock()
    camera[0].__fields__["wait_until_audio_completes"] = Mock()
    camera[0].stop_audio = AsyncMock()
    camera[0].play_audio = AsyncMock()
    camera[0].wait_until_audio_completes = AsyncMock()

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: camera[1],
            "media_content_id": "http://example.com/test.mp3",
            "media_content_type": "music",
        },
        blocking=True,
    )

    camera[0].play_audio.assert_called_once_with(
        "http://example.com/test.mp3", blocking=False
    )
    camera[0].wait_until_audio_completes.assert_called_once()


async def test_media_player_play_invalid(
    hass: HomeAssistant,
    camera: tuple[Camera, str],
):
    """Test media_player entity test play_media, not music."""

    camera[0].__fields__["play_audio"] = Mock()
    camera[0].play_audio = AsyncMock()

    with pytest.raises(ValueError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: camera[1],
                "media_content_id": "/test.png",
                "media_content_type": "image",
            },
            blocking=True,
        )

    assert not camera[0].play_audio.called


async def test_media_player_play_error(
    hass: HomeAssistant,
    camera: tuple[Camera, str],
):
    """Test media_player entity test play_media, not music."""

    camera[0].__fields__["play_audio"] = Mock()
    camera[0].__fields__["wait_until_audio_completes"] = Mock()
    camera[0].play_audio = AsyncMock(side_effect=StreamError)
    camera[0].wait_until_audio_completes = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: camera[1],
                "media_content_id": "/test.mp3",
                "media_content_type": "music",
            },
            blocking=True,
        )

    assert camera[0].play_audio.called
    assert not camera[0].wait_until_audio_completes.called
