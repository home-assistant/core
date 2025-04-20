"""Test the Teslemetry media player platform."""

from unittest.mock import AsyncMock, patch

import pytest
from syrupy.assertion import SnapshotAssertion
from teslemetry_stream import Signal

from homeassistant.components.media_player import (
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_VOLUME_SET,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import assert_entities, assert_entities_alt, reload_platform, setup_platform
from .const import COMMAND_OK, METADATA_NOSCOPE, VEHICLE_DATA_ALT


async def test_media_player(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the media player entities are correct."""

    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_alt(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_vehicle_data: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the media player entities are correct."""

    mock_vehicle_data.return_value = VEHICLE_DATA_ALT
    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities_alt(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_noscope(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_metadata: AsyncMock,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the media player entities are correct without required scope."""

    mock_metadata.return_value = METADATA_NOSCOPE
    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])
    assert_entities(hass, entry.entry_id, entity_registry, snapshot)


async def test_media_player_services(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_legacy: AsyncMock,
) -> None:
    """Tests that the media player services work."""

    await setup_platform(hass, [Platform.MEDIA_PLAYER])

    entity_id = "media_player.test_media_player"

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.adjust_volume",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_VOLUME_SET,
            {ATTR_ENTITY_ID: entity_id, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.5
        call.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.media_toggle_playback",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == MediaPlayerState.PAUSED
        call.assert_called_once()

    # This test will fail without the previous call to pause playback
    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.media_toggle_playback",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PLAY,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        assert state.state == MediaPlayerState.PLAYING
        call.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.media_next_track",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_NEXT_TRACK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        call.assert_called_once()

    with patch(
        "tesla_fleet_api.teslemetry.Vehicle.media_prev_track",
        return_value=COMMAND_OK,
    ) as call:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PREVIOUS_TRACK,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        state = hass.states.get(entity_id)
        call.assert_called_once()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_update_streaming(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    mock_vehicle_data: AsyncMock,
    mock_add_listener: AsyncMock,
) -> None:
    """Tests that the media player entities with streaming are correct."""

    entry = await setup_platform(hass, [Platform.MEDIA_PLAYER])

    # Stream update
    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.CENTER_DISPLAY: "Off",
                Signal.MEDIA_PLAYBACK_STATUS: None,
                Signal.MEDIA_PLAYBACK_SOURCE: None,
                Signal.MEDIA_AUDIO_VOLUME: None,
                Signal.MEDIA_NOW_PLAYING_DURATION: None,
                Signal.MEDIA_NOW_PLAYING_ELAPSED: None,
                Signal.MEDIA_NOW_PLAYING_ARTIST: None,
                Signal.MEDIA_NOW_PLAYING_ALBUM: None,
            },
            "createdAt": "2024-10-04T10:45:17.537Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_media_player")
    assert state == snapshot(name="off")

    mock_add_listener.send(
        {
            "vin": VEHICLE_DATA_ALT["response"]["vin"],
            "data": {
                Signal.CENTER_DISPLAY: "Driving",
                Signal.MEDIA_PLAYBACK_STATUS: "Playing",
                Signal.MEDIA_PLAYBACK_SOURCE: "Spotify",
                Signal.MEDIA_AUDIO_VOLUME: 2,
                Signal.MEDIA_NOW_PLAYING_DURATION: 60000,
                Signal.MEDIA_NOW_PLAYING_ELAPSED: 5000,
                Signal.MEDIA_NOW_PLAYING_ARTIST: "Test Artist",
                Signal.MEDIA_NOW_PLAYING_ALBUM: "Test Album",
            },
            "createdAt": "2024-10-04T10:55:17.000Z",
        }
    )
    await hass.async_block_till_done()
    state = hass.states.get("media_player.test_media_player")
    assert state == snapshot(name="on")

    await reload_platform(hass, entry, [Platform.MEDIA_PLAYER])

    # Ensure the restored state is the same as the previous state
    state = hass.states.get("media_player.test_media_player")
    assert state == snapshot(name="on")
