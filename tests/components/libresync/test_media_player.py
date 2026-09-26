"""Tests for the LibreSync media player."""

from datetime import timedelta
from unittest.mock import MagicMock

from aiolibresync import ConfirmationTimeout, NotConnectedError, NowPlaying, PlayState
from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_APP_NAME,
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_ALBUM_NAME,
    ATTR_MEDIA_ARTIST,
    ATTR_MEDIA_DURATION,
    ATTR_MEDIA_POSITION,
    ATTR_MEDIA_POSITION_UPDATED_AT,
    ATTR_MEDIA_TITLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_SELECT_SOURCE,
    SERVICE_VOLUME_SET,
    MediaPlayerState,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import STATE, push

from tests.common import MockConfigEntry, snapshot_platform

ENTITY_ID = "media_player.stereo"


@pytest.fixture(autouse=True)
async def setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: MagicMock
) -> None:
    """Set up the integration."""
    await setup_integration(hass, mock_config_entry)


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the media player entity and its state."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("play_state", "audio_state", "expected"),
    [
        # A physical input with nothing connected: the renderer says playing,
        # the audio activity report says idle, and the report is right.
        (PlayState.PLAYING, PlayState.IDLE, MediaPlayerState.IDLE),
        (PlayState.PLAYING, PlayState.PLAYING, MediaPlayerState.PLAYING),
        (PlayState.PAUSED, PlayState.PAUSED, MediaPlayerState.PAUSED),
        (PlayState.LOADING, PlayState.LOADING, MediaPlayerState.BUFFERING),
    ],
)
async def test_state(
    hass: HomeAssistant,
    mock_client: MagicMock,
    play_state: PlayState,
    audio_state: PlayState,
    expected: MediaPlayerState,
) -> None:
    """Test the state follows audio activity rather than the renderer."""
    push(mock_client, STATE.evolve(play_state=play_state, audio_state=audio_state))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == expected


async def test_unavailable(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the entity follows the connection, not the hub's power."""
    push(mock_client, STATE.evolve(power=False))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state != STATE_UNAVAILABLE

    push(mock_client, STATE.evolve(available=False))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE


async def test_select_source(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test a source is selected by the hub's index, not its list position."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "HDMI"},
        blocking=True,
    )
    mock_client.async_select_source.assert_awaited_once_with(6)


async def test_select_unknown_source(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test a source the hub does not report is refused."""
    with pytest.raises(ServiceValidationError) as raised:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SELECT_SOURCE,
            {ATTR_ENTITY_ID: ENTITY_ID, ATTR_INPUT_SOURCE: "Phono"},
            blocking=True,
        )
    assert raised.value.translation_key == "invalid_source"
    mock_client.async_select_source.assert_not_awaited()


async def test_set_volume(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the volume is sent in whole percent."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_MEDIA_VOLUME_LEVEL: 0.415},
        blocking=True,
    )
    mock_client.async_set_volume.assert_awaited_once_with(42)


@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_MEDIA_PLAY, "async_media_play"),
        (SERVICE_MEDIA_PAUSE, "async_media_pause"),
        (SERVICE_MEDIA_STOP, "async_media_stop"),
        (SERVICE_MEDIA_NEXT_TRACK, "async_media_next_track"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "async_media_previous_track"),
    ],
)
async def test_transport(
    hass: HomeAssistant, mock_client: MagicMock, service: str, method: str
) -> None:
    """Test the transport actions reach the hub."""
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN, service, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
    )
    getattr(mock_client, method).assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "key"),
    [
        (NotConnectedError("down"), "not_connected"),
        (ConfirmationTimeout("no echo"), "not_confirmed"),
    ],
)
async def test_command_errors(
    hass: HomeAssistant, mock_client: MagicMock, error: Exception, key: str
) -> None:
    """Test a failed command raises a translated error."""
    mock_client.async_media_pause.side_effect = error
    with pytest.raises(HomeAssistantError) as raised:
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_MEDIA_PAUSE,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
    assert raised.value.translation_key == key


async def test_now_playing(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the track metadata, with the position and duration in seconds."""
    push(
        mock_client,
        STATE.evolve(
            now_playing=NowPlaying(
                title="Track",
                artist="Artist",
                album="Album",
                artwork_url="http://192.168.1.50/art.jpg",
                duration_ms=315000,
                app="TIDAL",
            ),
            position_ms=61500,
        ),
    )
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_MEDIA_TITLE] == "Track"
    assert attributes[ATTR_MEDIA_ARTIST] == "Artist"
    assert attributes[ATTR_MEDIA_ALBUM_NAME] == "Album"
    assert attributes[ATTR_MEDIA_DURATION] == 315
    assert attributes[ATTR_MEDIA_POSITION] == 61
    assert attributes[ATTR_APP_NAME] == "TIDAL"


async def test_position_is_extrapolated(
    hass: HomeAssistant, mock_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a position that moves as expected is not written every second."""
    playing = STATE.evolve(
        play_state=PlayState.PLAYING, audio_state=PlayState.PLAYING, position_ms=10000
    )
    push(mock_client, playing)
    await hass.async_block_till_done()
    written = hass.states.get(ENTITY_ID)
    assert written.attributes[ATTR_MEDIA_POSITION] == 10

    freezer.tick(timedelta(seconds=1))
    push(mock_client, playing.evolve(position_ms=11000))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).last_updated == written.last_updated

    # A seek is written, with the time it was read.
    push(mock_client, playing.evolve(position_ms=90000))
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_MEDIA_POSITION] == 90
    assert (
        attributes[ATTR_MEDIA_POSITION_UPDATED_AT]
        > (written.attributes[ATTR_MEDIA_POSITION_UPDATED_AT])
    )


async def test_position_while_paused(
    hass: HomeAssistant, mock_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a position that moves while paused is written."""
    paused = STATE.evolve(position_ms=10000)
    push(mock_client, paused)
    await hass.async_block_till_done()

    freezer.tick(timedelta(seconds=1))
    push(mock_client, paused.evolve(position_ms=11000))
    await hass.async_block_till_done()
    assert hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_POSITION] == 11


async def test_position_time_kept_on_other_writes(
    hass: HomeAssistant, mock_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test a write for another reason keeps the time the position was read."""
    playing = STATE.evolve(
        play_state=PlayState.PLAYING, audio_state=PlayState.PLAYING, position_ms=10000
    )
    push(mock_client, playing)
    await hass.async_block_till_done()
    read_at = hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_POSITION_UPDATED_AT]

    freezer.tick(timedelta(milliseconds=900))
    push(mock_client, playing.evolve(volume=30))
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_MEDIA_VOLUME_LEVEL] == 0.3
    assert attributes[ATTR_MEDIA_POSITION_UPDATED_AT] == read_at


async def test_position_time_restamped_on_resume(
    hass: HomeAssistant, mock_client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Test resuming at the same position does not reuse the time of the pause."""
    playing = STATE.evolve(
        play_state=PlayState.PLAYING, audio_state=PlayState.PLAYING, position_ms=10000
    )
    paused = playing.evolve(play_state=PlayState.PAUSED, audio_state=PlayState.PAUSED)
    push(mock_client, paused)
    await hass.async_block_till_done()
    paused_at = hass.states.get(ENTITY_ID).attributes[ATTR_MEDIA_POSITION_UPDATED_AT]

    freezer.tick(timedelta(minutes=5))
    push(mock_client, playing)
    await hass.async_block_till_done()
    attributes = hass.states.get(ENTITY_ID).attributes
    assert attributes[ATTR_MEDIA_POSITION] == 10
    assert attributes[ATTR_MEDIA_POSITION_UPDATED_AT] - paused_at >= timedelta(
        minutes=5
    )
