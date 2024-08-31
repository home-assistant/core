"""Test the UniFi Protect media_player platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock, patch

import pytest
from pyunifiprotect.data import Camera
from pyunifiprotect.exceptions import StreamError

from homeassistant.components.media_player import (
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

from .utils import (
    MockUFPFixture,
    adopt_devices,
    assert_entity_counts,
    init_entry,
    remove_entities,
)


async def test_media_player_camera_remove(
    hass: HomeAssistant, ufp: MockUFPFixture, doorbell: Camera
) -> None:
    """Test removing and re-adding a light device."""

    await init_entry(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)
    await remove_entities(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 0, 0)
    await adopt_devices(hass, ufp, [doorbell])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)


async def test_media_player_setup(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity setup."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    unique_id = f"{doorbell.mac}_speaker"
    entity_id = "media_player.test_camera_speaker"

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get(entity_id)
    assert entity
    assert entity.unique_id == unique_id

    expected_volume = float(doorbell.speaker_settings.volume / 100)

    state = hass.states.get(entity_id)
    assert state
    assert state.state == STATE_IDLE
    assert state.attributes[ATTR_ATTRIBUTION] == DEFAULT_ATTRIBUTION
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == 136708
    assert state.attributes[ATTR_MEDIA_CONTENT_TYPE] == "music"
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == expected_volume


async def test_media_player_update(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity update."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    new_camera = doorbell.copy()
    new_camera.talkback_stream = Mock()
    new_camera.talkback_stream.is_running = True

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.test_camera_speaker")
    assert state
    assert state.state == STATE_PLAYING


async def test_media_player_set_volume(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test set_volume_level."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    doorbell.__fields__["set_speaker_volume"] = Mock(final=False)
    doorbell.set_speaker_volume = AsyncMock()

    await hass.services.async_call(
        "media_player",
        "volume_set",
        {ATTR_ENTITY_ID: "media_player.test_camera_speaker", "volume_level": 0.5},
        blocking=True,
    )

    doorbell.set_speaker_volume.assert_called_once_with(50)


async def test_media_player_stop(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test media_stop."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    new_camera = doorbell.copy()
    new_camera.talkback_stream = AsyncMock()
    new_camera.talkback_stream.is_running = True

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.new_obj = new_camera

    ufp.api.bootstrap.cameras = {new_camera.id: new_camera}
    ufp.ws_msg(mock_msg)
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "media_stop",
        {ATTR_ENTITY_ID: "media_player.test_camera_speaker"},
        blocking=True,
    )

    new_camera.talkback_stream.stop.assert_called_once()


async def test_media_player_play(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test play_media."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    doorbell.__fields__["stop_audio"] = Mock(final=False)
    doorbell.__fields__["play_audio"] = Mock(final=False)
    doorbell.__fields__["wait_until_audio_completes"] = Mock(final=False)
    doorbell.stop_audio = AsyncMock()
    doorbell.play_audio = AsyncMock()
    doorbell.wait_until_audio_completes = AsyncMock()

    await hass.services.async_call(
        "media_player",
        "play_media",
        {
            ATTR_ENTITY_ID: "media_player.test_camera_speaker",
            "media_content_id": "http://example.com/test.mp3",
            "media_content_type": "music",
        },
        blocking=True,
    )

    doorbell.play_audio.assert_called_once_with(
        "http://example.com/test.mp3", blocking=False
    )
    doorbell.wait_until_audio_completes.assert_called_once()


async def test_media_player_play_media_source(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test play_media."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    doorbell.__fields__["stop_audio"] = Mock(final=False)
    doorbell.__fields__["play_audio"] = Mock(final=False)
    doorbell.__fields__["wait_until_audio_completes"] = Mock(final=False)
    doorbell.stop_audio = AsyncMock()
    doorbell.play_audio = AsyncMock()
    doorbell.wait_until_audio_completes = AsyncMock()

    with patch(
        "homeassistant.components.media_source.async_resolve_media",
        return_value=Mock(url="http://example.com/test.mp3"),
    ):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: "media_player.test_camera_speaker",
                "media_content_id": "media-source://some_source/some_id",
                "media_content_type": "audio/mpeg",
            },
            blocking=True,
        )

    doorbell.play_audio.assert_called_once_with(
        "http://example.com/test.mp3", blocking=False
    )
    doorbell.wait_until_audio_completes.assert_called_once()


async def test_media_player_play_invalid(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test play_media, not music."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    doorbell.__fields__["play_audio"] = Mock(final=False)
    doorbell.play_audio = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: "media_player.test_camera_speaker",
                "media_content_id": "/test.png",
                "media_content_type": "image",
            },
            blocking=True,
        )

    assert not doorbell.play_audio.called


async def test_media_player_play_error(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
    doorbell: Camera,
    unadopted_camera: Camera,
) -> None:
    """Test media_player entity test play_media, not music."""

    await init_entry(hass, ufp, [doorbell, unadopted_camera])
    assert_entity_counts(hass, Platform.MEDIA_PLAYER, 1, 1)

    doorbell.__fields__["play_audio"] = Mock(final=False)
    doorbell.__fields__["wait_until_audio_completes"] = Mock(final=False)
    doorbell.play_audio = AsyncMock(side_effect=StreamError)
    doorbell.wait_until_audio_completes = AsyncMock()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                ATTR_ENTITY_ID: "media_player.test_camera_speaker",
                "media_content_id": "/test.mp3",
                "media_content_type": "music",
            },
            blocking=True,
        )

    assert doorbell.play_audio.called
    assert not doorbell.wait_until_audio_completes.called
