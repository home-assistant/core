"""Test the HiFiBerry media player platform."""

from unittest.mock import MagicMock

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PLAY_PAUSE,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    MediaPlayerEntityFeature,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_SUPPORTED_FEATURES
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

ENTITY_ID = "media_player.kitchen_speaker"


async def test_media_player_state(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test media player state and attributes."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state.state == MediaPlayerState.PLAYING
    assert state.attributes[ATTR_MEDIA_TITLE] == "Big Love"
    assert state.attributes[ATTR_MEDIA_ARTIST] == "Fleetwood Mac"
    assert state.attributes[ATTR_MEDIA_ALBUM_NAME] == "Greatest Hits"
    assert state.attributes[ATTR_INPUT_SOURCE] == "spotify"
    assert state.attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.8
    assert state.attributes[ATTR_MEDIA_VOLUME_MUTED] is False
    assert state.attributes["entity_picture"] == "https://example.com/cover.jpg"
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == int(
        MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.STOP
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.VOLUME_STEP
    )


async def test_media_player_dynamic_capabilities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test controls are exposed from active player capabilities."""
    mock_audiocontrol_client.active_player_capabilities = {"play", "pause", "stop"}
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    features = MediaPlayerEntityFeature(state.attributes[ATTR_SUPPORTED_FEATURES])
    assert features & MediaPlayerEntityFeature.PLAY
    assert features & MediaPlayerEntityFeature.PAUSE
    assert features & MediaPlayerEntityFeature.STOP
    assert not features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not features & MediaPlayerEntityFeature.PREVIOUS_TRACK


async def test_media_player_services(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_audiocontrol_client: MagicMock,
) -> None:
    """Test media player service calls."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for service, command in (
        (SERVICE_MEDIA_PAUSE, "pause"),
        (SERVICE_MEDIA_PLAY, "play"),
        (SERVICE_MEDIA_STOP, "stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "next"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous"),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
        mock_audiocontrol_client.async_command.assert_awaited_with(command)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY_PAUSE,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )
    mock_audiocontrol_client.async_command.assert_awaited_with("pause")

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        blocking=True,
    )
    mock_audiocontrol_client.async_set_volume.assert_awaited_with(50)

    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_MUTED: True},
        blocking=True,
    )
    mock_audiocontrol_client.async_set_volume.assert_awaited_with(0)
