"""Tests for the Spotify media player platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from spotifyaio import (
    PlaybackState,
    ProductType,
    RepeatMode as SpotifyRepeatMode,
    SpotifyConnectionError,
    SpotifyNotFoundError,
)
from syrupy import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_INPUT_SOURCE_LIST,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_ENQUEUE,
    ATTR_MEDIA_REPEAT,
    ATTR_MEDIA_SEEK_POSITION,
    ATTR_MEDIA_SHUFFLE,
    ATTR_MEDIA_VOLUME_LEVEL,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    MediaPlayerEnqueue,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
    RepeatMode,
)
from homeassistant.components.spotify import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ENTITY_PICTURE,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_SEEK,
    SERVICE_REPEAT_SET,
    SERVICE_SHUFFLE_SET,
    SERVICE_VOLUME_SET,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import (
    MockConfigEntry,
    async_fire_time_changed,
    load_fixture,
    snapshot_platform,
)


@pytest.mark.usefixtures("setup_credentials")
async def test_entities(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities."""
    freezer.move_to("2023-10-21")
    with (
        patch("secrets.token_hex", return_value="mock-token"),
        patch("homeassistant.components.spotify.PLATFORMS", [Platform.MEDIA_PLAYER]),
    ):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_podcast(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Spotify entities while listening a podcast."""
    freezer.move_to("2023-10-21")
    mock_spotify.return_value.get_playback.return_value = PlaybackState.from_json(
        load_fixture("playback_episode.json", DOMAIN)
    )
    with (
        patch("secrets.token_hex", return_value="mock-token"),
        patch("homeassistant.components.spotify.PLATFORMS", [Platform.MEDIA_PLAYER]),
    ):
        await setup_integration(hass, mock_config_entry)

        await snapshot_platform(
            hass, entity_registry, snapshot, mock_config_entry.entry_id
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_free_account(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities with a free account."""
    mock_spotify.return_value.get_current_user.return_value.product = ProductType.FREE
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["supported_features"] == 0


@pytest.mark.usefixtures("setup_credentials")
async def test_restricted_device(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities with a restricted device."""
    mock_spotify.return_value.get_playback.return_value.device.is_restricted = True
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert (
        state.attributes["supported_features"] == MediaPlayerEntityFeature.SELECT_SOURCE
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_spotify_dj_list(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Spotify entities with a Spotify DJ playlist."""
    mock_spotify.return_value.get_playback.return_value.context.uri = (
        "spotify:playlist:37i9dQZF1EYkqdzj48dyYq"
    )
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["media_playlist"] == "DJ"

    mock_spotify.return_value.get_playlist.assert_not_called()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["media_playlist"] == "DJ"

    mock_spotify.return_value.get_playlist.assert_not_called()


@pytest.mark.usefixtures("setup_credentials")
async def test_normal_playlist(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test normal playlist switching."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["media_playlist"] == "Spotify Web API Testing playlist"

    mock_spotify.return_value.get_playlist.assert_called_once_with(
        "spotify:user:rushofficial:playlist:2r35vbe6hHl6yDSMfjKgmm"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.attributes["media_playlist"] == "Spotify Web API Testing playlist"

    mock_spotify.return_value.get_playlist.assert_called_once_with(
        "spotify:user:rushofficial:playlist:2r35vbe6hHl6yDSMfjKgmm"
    )

    mock_spotify.return_value.get_playback.return_value.context.uri = (
        "spotify:playlist:123123123123123"
    )

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_spotify.return_value.get_playlist.assert_called_with(
        "spotify:playlist:123123123123123"
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_fetching_playlist_does_not_fail(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test failing fetching playlist does not fail update."""
    mock_spotify.return_value.get_playlist.side_effect = SpotifyConnectionError
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert "media_playlist" not in state.attributes

    mock_spotify.return_value.get_playlist.assert_called_once()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_spotify.return_value.get_playlist.call_count == 2


@pytest.mark.usefixtures("setup_credentials")
async def test_fetching_playlist_once(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that not being able to find a playlist doesn't retry."""
    mock_spotify.return_value.get_playlist.side_effect = SpotifyNotFoundError
    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert "media_playlist" not in state.attributes

    mock_spotify.return_value.get_playlist.assert_called_once()

    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert "media_playlist" not in state.attributes

    mock_spotify.return_value.get_playlist.assert_called_once()


@pytest.mark.usefixtures("setup_credentials")
async def test_idle(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify entities in idle state."""
    mock_spotify.return_value.get_playback.return_value = {}
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.state == MediaPlayerState.IDLE
    assert (
        state.attributes["supported_features"] == MediaPlayerEntityFeature.SELECT_SOURCE
    )


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("service", "method"),
    [
        (SERVICE_MEDIA_PLAY, "start_playback"),
        (SERVICE_MEDIA_PAUSE, "pause_playback"),
        (SERVICE_MEDIA_PREVIOUS_TRACK, "previous_track"),
        (SERVICE_MEDIA_NEXT_TRACK, "next_track"),
    ],
)
async def test_simple_actions(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    service: str,
    method: str,
) -> None:
    """Test the Spotify media player."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: "media_player.spotify_spotify_1"},
        blocking=True,
    )
    getattr(mock_spotify.return_value, method).assert_called_once_with()


@pytest.mark.usefixtures("setup_credentials")
async def test_repeat_mode(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player repeat mode."""
    await setup_integration(hass, mock_config_entry)
    for mode, spotify_mode in (
        (RepeatMode.ALL, SpotifyRepeatMode.CONTEXT),
        (RepeatMode.ONE, SpotifyRepeatMode.TRACK),
        (RepeatMode.OFF, SpotifyRepeatMode.OFF),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_REPEAT_SET,
            {ATTR_ENTITY_ID: "media_player.spotify_spotify_1", ATTR_MEDIA_REPEAT: mode},
            blocking=True,
        )
        mock_spotify.return_value.set_repeat.assert_called_once_with(spotify_mode)
        mock_spotify.return_value.set_repeat.reset_mock()


@pytest.mark.usefixtures("setup_credentials")
async def test_shuffle(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player shuffle."""
    await setup_integration(hass, mock_config_entry)
    for shuffle in (True, False):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_SHUFFLE_SET,
            {
                ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
                ATTR_MEDIA_SHUFFLE: shuffle,
            },
            blocking=True,
        )
        mock_spotify.return_value.set_shuffle.assert_called_once_with(state=shuffle)
        mock_spotify.return_value.set_shuffle.reset_mock()


@pytest.mark.usefixtures("setup_credentials")
async def test_volume_level(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player volume level."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_MEDIA_VOLUME_LEVEL: 0.5,
        },
        blocking=True,
    )
    mock_spotify.return_value.set_volume.assert_called_with(50)


@pytest.mark.usefixtures("setup_credentials")
async def test_seek(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player seeking."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_SEEK,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_MEDIA_SEEK_POSITION: 100,
        },
        blocking=True,
    )
    mock_spotify.return_value.seek_track.assert_called_with(100000)


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("media_type", "media_id"),
    [
        ("spotify://track", "spotify:track:3oRoMXsP2NRzm51lldj1RO"),
        ("spotify://episode", "spotify:episode:3oRoMXsP2NRzm51lldj1RO"),
        (MediaType.MUSIC, "spotify:track:3oRoMXsP2NRzm51lldj1RO"),
    ],
)
async def test_play_media_in_queue(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_type: str,
    media_id: str,
) -> None:
    """Test the Spotify media player play media."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
            ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD,
        },
        blocking=True,
    )
    mock_spotify.return_value.add_to_queue.assert_called_with(media_id, None)


@pytest.mark.usefixtures("setup_credentials")
@pytest.mark.parametrize(
    ("media_type", "media_id", "called_with"),
    [
        (
            "spotify://artist",
            "spotify:artist:74Yus6IHfa3tWZzXXAYtS2",
            {"context_uri": "spotify:artist:74Yus6IHfa3tWZzXXAYtS2"},
        ),
        (
            "spotify://playlist",
            "spotify:playlist:74Yus6IHfa3tWZzXXAYtS2",
            {"context_uri": "spotify:playlist:74Yus6IHfa3tWZzXXAYtS2"},
        ),
        (
            "spotify://album",
            "spotify:album:74Yus6IHfa3tWZzXXAYtS2",
            {"context_uri": "spotify:album:74Yus6IHfa3tWZzXXAYtS2"},
        ),
        (
            "spotify://show",
            "spotify:show:74Yus6IHfa3tWZzXXAYtS2",
            {"context_uri": "spotify:show:74Yus6IHfa3tWZzXXAYtS2"},
        ),
        (
            MediaType.MUSIC,
            "spotify:track:3oRoMXsP2NRzm51lldj1RO",
            {"uris": ["spotify:track:3oRoMXsP2NRzm51lldj1RO"]},
        ),
        (
            "spotify://track",
            "spotify:track:3oRoMXsP2NRzm51lldj1RO",
            {"uris": ["spotify:track:3oRoMXsP2NRzm51lldj1RO"]},
        ),
        (
            "spotify://episode",
            "spotify:episode:3oRoMXsP2NRzm51lldj1RO",
            {"uris": ["spotify:episode:3oRoMXsP2NRzm51lldj1RO"]},
        ),
    ],
)
async def test_play_media(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    media_type: str,
    media_id: str,
    called_with: dict,
) -> None:
    """Test the Spotify media player play media."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_MEDIA_CONTENT_TYPE: media_type,
            ATTR_MEDIA_CONTENT_ID: media_id,
        },
        blocking=True,
    )
    mock_spotify.return_value.start_playback.assert_called_with(**called_with)


@pytest.mark.usefixtures("setup_credentials")
async def test_add_unsupported_media_to_queue(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player add unsupported media to queue."""
    await setup_integration(hass, mock_config_entry)
    with pytest.raises(
        ValueError, match="Media type playlist is not supported when enqueue is ADD"
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
                ATTR_MEDIA_CONTENT_TYPE: "spotify://playlist",
                ATTR_MEDIA_CONTENT_ID: "spotify:playlist:74Yus6IHfa3tWZzXXAYtS2",
                ATTR_MEDIA_ENQUEUE: MediaPlayerEnqueue.ADD,
            },
            blocking=True,
        )


@pytest.mark.usefixtures("setup_credentials")
async def test_play_unsupported_media(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player play media."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_MEDIA_CONTENT_TYPE: MediaType.COMPOSER,
            ATTR_MEDIA_CONTENT_ID: "spotify:track:3oRoMXsP2NRzm51lldj1RO",
        },
        blocking=True,
    )
    assert mock_spotify.return_value.start_playback.call_count == 0
    assert mock_spotify.return_value.add_to_queue.call_count == 0


@pytest.mark.usefixtures("setup_credentials")
async def test_select_source(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player source select."""
    await setup_integration(hass, mock_config_entry)
    await hass.services.async_call(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {
            ATTR_ENTITY_ID: "media_player.spotify_spotify_1",
            ATTR_INPUT_SOURCE: "DESKTOP-BKC5SIK",
        },
        blocking=True,
    )
    mock_spotify.return_value.transfer_playback.assert_called_with(
        "21dac6b0e0a1f181870fdc9749b2656466557666"
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_source_devices(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the Spotify media player available source devices."""
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")

    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["DESKTOP-BKC5SIK"]

    mock_spotify.return_value.get_devices.side_effect = SpotifyConnectionError
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.state != STATE_UNAVAILABLE
    assert state.attributes[ATTR_INPUT_SOURCE_LIST] == ["DESKTOP-BKC5SIK"]


@pytest.mark.usefixtures("setup_credentials")
async def test_paused_playback(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player with paused playback."""
    mock_spotify.return_value.get_playback.return_value.is_playing = False
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert state.state == MediaPlayerState.PAUSED


@pytest.mark.usefixtures("setup_credentials")
async def test_fallback_show_image(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player with a fallback image."""
    playback = PlaybackState.from_json(load_fixture("playback_episode.json", DOMAIN))
    playback.item.images = []
    mock_spotify.return_value.get_playback.return_value = playback
    with patch("secrets.token_hex", return_value="mock-token"):
        await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert (
        state.attributes[ATTR_ENTITY_PICTURE]
        == "/api/media_player_proxy/media_player.spotify_spotify_1?token=mock-token&cache=16ff384dbae94fea"
    )


@pytest.mark.usefixtures("setup_credentials")
async def test_no_episode_images(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player with no episode images."""
    playback = PlaybackState.from_json(load_fixture("playback_episode.json", DOMAIN))
    playback.item.images = []
    playback.item.show.images = []
    mock_spotify.return_value.get_playback.return_value = playback
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert ATTR_ENTITY_PICTURE not in state.attributes


@pytest.mark.usefixtures("setup_credentials")
async def test_no_album_images(
    hass: HomeAssistant,
    mock_spotify: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the Spotify media player with no album images."""
    mock_spotify.return_value.get_playback.return_value.item.album.images = []
    await setup_integration(hass, mock_config_entry)
    state = hass.states.get("media_player.spotify_spotify_1")
    assert state
    assert ATTR_ENTITY_PICTURE not in state.attributes
