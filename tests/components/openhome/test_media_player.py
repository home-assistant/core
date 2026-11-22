"""Tests for the Openhome media player platform."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from openhomedevice.device import Device
from openhomedevice.exceptions import OpenhomeConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.media_player import (
    ATTR_INPUT_SOURCE,
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_VOLUME_LEVEL,
    ATTR_MEDIA_VOLUME_MUTED,
    DOMAIN as MEDIA_PLAYER_DOMAIN,
    SERVICE_PLAY_MEDIA,
    SERVICE_SELECT_SOURCE,
    BrowseError,
    MediaType,
)
from homeassistant.components.media_source import PlayMedia
from homeassistant.components.openhome.const import (
    DOMAIN,
    OpenhomeService,
    OpenhomeServiceArgument,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_MEDIA_NEXT_TRACK,
    SERVICE_MEDIA_PAUSE,
    SERVICE_MEDIA_PLAY,
    SERVICE_MEDIA_PREVIOUS_TRACK,
    SERVICE_MEDIA_STOP,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    SERVICE_VOLUME_DOWN,
    SERVICE_VOLUME_MUTE,
    SERVICE_VOLUME_SET,
    SERVICE_VOLUME_UP,
    STATE_IDLE,
    STATE_OFF,
    STATE_PAUSED,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    Platform,
    TargetKey,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import async_poll, setup_integration
from .conftest import TRACK_INFO

ENTITY_ID = "media_player.friendly_name"
MEDIA_ID = "http://localhost/track.flac"

# Each action, the coroutine it drives, a source type that exposes the supported
# feature it is gated behind, and the arguments the device must be called with.
ACTIONS = [
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_ON,
        {},
        Device.set_standby,
        "Playlist",
        (False,),
        id="turn_on",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_TURN_OFF,
        {},
        Device.set_standby,
        "Playlist",
        (True,),
        id="turn_off",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PLAY,
        {},
        Device.play,
        "Playlist",
        (),
        id="media_play",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PAUSE,
        {},
        Device.pause,
        "Playlist",
        (),
        id="media_pause",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_STOP,
        {},
        Device.stop,
        "Radio",
        (),
        id="media_stop",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_NEXT_TRACK,
        {},
        Device.skip,
        "Playlist",
        (1,),
        id="media_next_track",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_MEDIA_PREVIOUS_TRACK,
        {},
        Device.skip,
        "Playlist",
        (-1,),
        id="media_previous_track",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_UP,
        {},
        Device.increase_volume,
        "Playlist",
        (),
        id="volume_up",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_DOWN,
        {},
        Device.decrease_volume,
        "Playlist",
        (),
        id="volume_down",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_SET,
        {ATTR_MEDIA_VOLUME_LEVEL: 0.5},
        Device.set_volume,
        "Playlist",
        (50,),
        id="volume_set",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: True},
        Device.set_mute,
        "Playlist",
        (True,),
        id="volume_mute",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_VOLUME_MUTE,
        {ATTR_MEDIA_VOLUME_MUTED: False},
        Device.set_mute,
        "Playlist",
        (False,),
        id="volume_unmute",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_SELECT_SOURCE,
        {ATTR_INPUT_SOURCE: "Radio"},
        Device.set_source,
        "Playlist",
        (1,),
        id="select_source",
    ),
    pytest.param(
        MEDIA_PLAYER_DOMAIN,
        SERVICE_PLAY_MEDIA,
        {
            ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
            ATTR_MEDIA_CONTENT_ID: MEDIA_ID,
        },
        Device.play_media,
        "Playlist",
        ({"title": "Home Assistant", "uri": MEDIA_ID, "albumArtwork": ""},),
        id="play_media",
    ),
]


@pytest.fixture(autouse=True)
def media_proxy_token() -> Generator[None]:
    """Freeze the media proxy token, which otherwise varies per run."""
    with patch("secrets.token_hex", return_value="mock_token"):
        yield


@pytest.fixture
def platforms() -> list[Platform]:
    """Only load the media player platform."""
    return [Platform.MEDIA_PLAYER]


async def setup_media_player(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Load the media player platform and poll once."""
    await setup_integration(hass, mock_config_entry)

    # Supported features are only set once the device has been polled.
    await async_poll(hass)


@pytest.mark.parametrize(
    ("domain", "service", "data", "method", "source_type", "expected_args"), ACTIONS
)
async def test_action_calls_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    domain: str,
    service: str,
    data: dict[str, Any],
    method: Callable[..., Any],
    source_type: str,
    expected_args: tuple[Any, ...],
) -> None:
    """Test every action calls the device with the arguments it expects."""
    mock_device.source.return_value = {
        "index": 0,
        "name": source_type,
        "type": source_type,
    }

    await setup_media_player(hass, mock_config_entry)

    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
    )

    getattr(mock_device, method.__name__).assert_awaited_once_with(*expected_args)


@pytest.mark.parametrize(
    ("domain", "service", "data", "method", "source_type", "expected_args"), ACTIONS
)
async def test_action_error_is_raised(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    domain: str,
    service: str,
    data: dict[str, Any],
    method: Callable[..., Any],
    source_type: str,
    expected_args: tuple[Any, ...],
) -> None:
    """Test every action raises when the device rejects the request."""
    # The feature each action is gated behind depends on the selected source.
    mock_device.source.return_value = {
        "index": 0,
        "name": source_type,
        "type": source_type,
    }

    await setup_media_player(hass, mock_config_entry)

    mocked = getattr(mock_device, method.__name__)
    mocked.side_effect = OpenhomeConnectionError("no route to host")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: ENTITY_ID, **data}, blocking=True
        )

    # The message is keyed on the service name, so each action reports its own.
    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == service
    mocked.assert_awaited()


async def test_play_media_media_source_keeps_media_metadata(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a media library item is played with its own title and artwork."""
    await setup_media_player(hass, mock_config_entry)

    browsed = MagicMock(
        title="Track Title", thumbnail="http://localhost/art.jpg", can_expand=False
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(return_value=browsed),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(
                return_value=PlayMedia(
                    "http://localhost/media/track.flac", "audio/flac"
                )
            ),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://media_source/music/track.flac",
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Track Title",
            "uri": "http://localhost/media/track.flac",
            "albumArtwork": "http://localhost/art.jpg",
        }
    )


async def test_play_media_station_found_in_source_listing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a station browsed as a listing gets its name and icon in the metadata."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/station-uuid"
    station = MagicMock(
        media_content_id=station_id,
        title="France Inter",
        thumbnail="http://localhost/france-inter.ico",
        can_play=True,
        can_expand=False,
    )
    category = MagicMock(
        media_content_id="media-source://radio_browser/popular", can_expand=True
    )
    category_listing = MagicMock(can_expand=True, children=[station])
    root_listing = MagicMock(can_expand=True, children=[category])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == category.media_content_id:
            return category_listing
        if media_content_id == station_id:
            # radio_browser returns an empty listing for a station id
            return MagicMock(can_expand=True, children=[])
        return root_listing

    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(
                return_value=PlayMedia(
                    "http://stream.example/france-inter", "audio/mpeg"
                )
            ),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "France Inter",
            "uri": "http://stream.example/france-inter",
            "albumArtwork": "http://localhost/france-inter.ico",
        }
    )


async def test_play_media_browse_failure_still_plays(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test playback still works when browsing the item fails.

    DLNA servers answer upnp error 710 (No such container) when browsing the
    direct children of a file, so the metadata lookup must not fail play_media.
    The title and artwork then come from the resolved DIDL metadata.
    """
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="NAS Track", album_art_uri="http://nas:5000/art.jpg")
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac", didl_metadata=didl, thumbnail=None
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=BrowseError("Server failure: upnp error 710")),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms/nas/:some-object-id",
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/art.jpg",
        }
    )


async def test_play_media_browse_failure_resolves_relative_artwork(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test relative DIDL artwork URLs are resolved against the media server URL."""
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="NAS Track", album_art_uri="/upnp/art.jpg")
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac", didl_metadata=didl, thumbnail=None
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=BrowseError("Server failure: upnp error 710")),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms/nas/:some-object-id",
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/upnp/art.jpg",
        }
    )


async def test_play_media_browse_failure_uses_parent_listing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a file is looked up in its parent listing when direct browse fails."""
    await setup_media_player(hass, mock_config_entry)

    media_content_id = "media-source://media_source/music/track.flac"
    parent_id = "media-source://media_source/music"
    track = MagicMock(
        media_content_id=media_content_id,
        title="Local Track",
        thumbnail="http://localhost/art.jpg",
        can_play=True,
        can_expand=False,
    )
    parent_listing = MagicMock(can_expand=True, children=[track])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == parent_id:
            return parent_listing
        raise BrowseError("Server failure: upnp error 710")

    play_item = MagicMock(url="http://localhost/media/track.flac", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: media_content_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Local Track",
            "uri": "http://localhost/media/track.flac",
            "albumArtwork": "http://localhost/art.jpg",
        }
    )


async def test_play_media_metadata_search_is_bounded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test the source-tree metadata search stops after a bounded number of requests."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/missing-station"
    children = [
        MagicMock(
            media_content_id=f"media-source://radio_browser/cat-{idx}",
            can_expand=True,
        )
        for idx in range(50)
    ]
    listing = MagicMock(can_expand=True, children=children)
    empty_listing = MagicMock(can_expand=True, children=[])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id.startswith("media-source://radio_browser/cat-"):
            return empty_listing
        return listing

    browse_mock = AsyncMock(side_effect=browse_side_effect)
    play_item = MagicMock(url="http://stream.example/missing", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            browse_mock,
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    # 1 browse of the item + 1 of the domain root + at most the request budget.
    assert browse_mock.call_count <= 2 + 20
    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Home Assistant",
            "uri": "http://stream.example/missing",
            "albumArtwork": "",
        }
    )


async def test_play_media_browse_failure_prefers_normalized_thumbnail(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test the source-normalized thumbnail wins over raw DIDL artwork."""
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="NAS Track", album_art_uri="/upnp/art.jpg")
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac",
        didl_metadata=didl,
        thumbnail="http://nas:5000/upnp/normalized.jpg",
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=BrowseError("Server failure: upnp error 710")),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms/nas/:some-object-id",
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/upnp/normalized.jpg",
        }
    )


async def test_play_media_root_browse_failure_still_plays(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test a failing media source root browse does not abort playback."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/station-uuid"
    listing = MagicMock(can_expand=True, children=[])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == station_id:
            return listing
        raise BrowseError("Server failure: root unavailable")

    play_item = MagicMock(url="http://stream.example/station", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Home Assistant",
            "uri": "http://stream.example/station",
            "albumArtwork": "",
        }
    )


async def test_play_media_search_continues_after_branch_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test the metadata search skips branches that fail to browse."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/station-uuid"
    station = MagicMock(
        media_content_id=station_id,
        title="France Inter",
        thumbnail="http://localhost/france-inter.ico",
        can_play=True,
        can_expand=False,
    )
    broken_category = MagicMock(
        media_content_id="media-source://radio_browser/broken", can_expand=True
    )
    good_category = MagicMock(
        media_content_id="media-source://radio_browser/popular", can_expand=True
    )
    good_listing = MagicMock(can_expand=True, children=[station])
    root_listing = MagicMock(can_expand=True, children=[broken_category, good_category])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == station_id:
            return MagicMock(can_expand=True, children=[])
        if media_content_id == broken_category.media_content_id:
            raise BrowseError("Server failure: upnp error 710")
        if media_content_id == good_category.media_content_id:
            return good_listing
        return root_listing

    play_item = MagicMock(url="http://stream.example/france-inter", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "France Inter",
            "uri": "http://stream.example/france-inter",
            "albumArtwork": "http://localhost/france-inter.ico",
        }
    )


async def test_play_media_search_processes_final_permitted_browse(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test results of the last browse allowed by the budget are still searched."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/station-uuid"
    station = MagicMock(
        media_content_id=station_id,
        title="Last Budget Station",
        thumbnail="http://localhost/last.ico",
        can_play=True,
        can_expand=False,
    )
    # 19 empty categories, then the station inside the 20th (last permitted) browse.
    categories = [
        MagicMock(
            media_content_id=f"media-source://radio_browser/cat-{idx}", can_expand=True
        )
        for idx in range(19)
    ]
    last_category = MagicMock(
        media_content_id="media-source://radio_browser/cat-last", can_expand=True
    )
    last_listing = MagicMock(can_expand=True, children=[station])
    root_listing = MagicMock(can_expand=True, children=[*categories, last_category])
    empty_listing = MagicMock(can_expand=True, children=[])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == station_id:
            return empty_listing
        if media_content_id == last_category.media_content_id:
            return last_listing
        if media_content_id.startswith("media-source://radio_browser/cat-"):
            return empty_listing
        return root_listing

    play_item = MagicMock(url="http://stream.example/last", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Last Budget Station",
            "uri": "http://stream.example/last",
            "albumArtwork": "http://localhost/last.ico",
        }
    )


async def test_play_media_skips_browse_when_resolved_metadata_complete(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test no browse request is made when the resolved item has title and artwork."""
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="NAS Track", album_art_uri="/upnp/art.jpg")
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac",
        didl_metadata=didl,
        thumbnail="http://nas:5000/upnp/normalized.jpg",
    )
    browse_mock = AsyncMock()
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            browse_mock,
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms/nas/:some-object-id",
            },
            blocking=True,
        )

    browse_mock.assert_not_called()
    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/upnp/normalized.jpg",
        }
    )


async def test_play_media_browses_when_resolved_metadata_incomplete(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test browsing still happens when the resolved item lacks artwork."""
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="NAS Track", album_art_uri=None)
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac", didl_metadata=didl, thumbnail=None
    )
    browsed = MagicMock(
        title="NAS Track", thumbnail="http://nas:5000/art.jpg", can_expand=False
    )
    browse_mock = AsyncMock(return_value=browsed)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            browse_mock,
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms/nas/:some-object-id",
            },
            blocking=True,
        )

    browse_mock.assert_called_once()
    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/art.jpg",
        }
    )


async def test_play_media_parent_listing_without_match_falls_back_to_didl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test DIDL fallback when the parent listing does not contain the item."""
    await setup_media_player(hass, mock_config_entry)

    media_content_id = "media-source://media_source/music/track.flac"
    parent_id = "media-source://media_source/music"
    other = MagicMock(
        media_content_id="media-source://media_source/music/other.flac",
        can_expand=False,
    )
    parent_listing = MagicMock(can_expand=True, children=[other])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id == parent_id:
            return parent_listing
        raise BrowseError("Server failure: upnp error 710")

    didl = MagicMock(title="NAS Track", album_art_uri="http://nas:5000/art.jpg")
    play_item = MagicMock(
        url="http://nas:5000/music/track.flac", didl_metadata=didl, thumbnail=None
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: media_content_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "NAS Track",
            "uri": "http://nas:5000/music/track.flac",
            "albumArtwork": "http://nas:5000/art.jpg",
        }
    )


async def test_play_media_browse_failure_without_parent_falls_back_to_didl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test DIDL fallback when the media id has no parent to look up."""
    await setup_media_player(hass, mock_config_entry)

    didl = MagicMock(title="Radio", album_art_uri="http://nas:5000/a.jpg")
    play_item = MagicMock(
        url="http://nas:5000/stream", didl_metadata=didl, thumbnail=None
    )
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=BrowseError("Server failure: upnp error 710")),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: "media-source://dlna_dms",
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Radio",
            "uri": "http://nas:5000/stream",
            "albumArtwork": "http://nas:5000/a.jpg",
        }
    )


async def test_play_media_search_stops_at_depth_limit(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
) -> None:
    """Test the metadata search does not expand branches beyond the depth limit."""
    await setup_media_player(hass, mock_config_entry)

    station_id = "media-source://radio_browser/deep-station"
    station = MagicMock(
        media_content_id=station_id,
        title="Deep Station",
        can_play=True,
        can_expand=False,
    )
    level2 = MagicMock(
        media_content_id="media-source://radio_browser/l2", can_expand=True
    )
    level1 = MagicMock(
        media_content_id="media-source://radio_browser/l1", can_expand=True
    )
    level0 = MagicMock(
        media_content_id="media-source://radio_browser/l0", can_expand=True
    )
    listings = {
        station_id: MagicMock(can_expand=True, children=[]),
        level2.media_content_id: MagicMock(can_expand=True, children=[station]),
        level1.media_content_id: MagicMock(can_expand=True, children=[level2]),
        level0.media_content_id: MagicMock(can_expand=True, children=[level1]),
    }
    root_listing = MagicMock(can_expand=True, children=[level0])

    async def browse_side_effect(
        hass: HomeAssistant, media_content_id: str, **kwargs: Any
    ) -> MagicMock:
        if media_content_id in listings:
            return listings[media_content_id]
        return root_listing

    play_item = MagicMock(url="http://stream.example/deep", didl_metadata=None)
    with (
        patch(
            "homeassistant.components.media_source.async_browse_media",
            AsyncMock(side_effect=browse_side_effect),
        ),
        patch(
            "homeassistant.components.media_source.async_resolve_media",
            AsyncMock(return_value=play_item),
        ),
    ):
        await hass.services.async_call(
            MEDIA_PLAYER_DOMAIN,
            SERVICE_PLAY_MEDIA,
            {
                ATTR_ENTITY_ID: ENTITY_ID,
                ATTR_MEDIA_CONTENT_TYPE: MediaType.MUSIC,
                ATTR_MEDIA_CONTENT_ID: station_id,
            },
            blocking=True,
        )

    mock_device.play_media.assert_awaited_once_with(
        {
            "title": "Home Assistant",
            "uri": "http://stream.example/deep",
            "albumArtwork": "",
        }
    )


async def test_invoke_pin_calls_device(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_device: MagicMock
) -> None:
    """Test the invoke_pin action passes the requested pin to the device."""
    await setup_media_player(hass, mock_config_entry)

    await hass.services.async_call(
        DOMAIN,
        OpenhomeService.INVOKE_PIN,
        {TargetKey.ENTITY_ID: ENTITY_ID, OpenhomeServiceArgument.PIN: 3},
        blocking=True,
    )

    mock_device.invoke_pin.assert_awaited_once_with(3)


@pytest.mark.parametrize(
    ("pins_enabled", "translation_key", "await_count"),
    [
        pytest.param(True, "invoke_pin", 1, id="pins_supported"),
        pytest.param(False, "pins_not_supported", 0, id="pins_not_supported"),
    ],
)
async def test_invoke_pin(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    pins_enabled: bool,
    translation_key: str,
    await_count: int,
) -> None:
    """Test invoking a pin on a device with and without pin support."""
    mock_device.pins_enabled = pins_enabled

    await setup_media_player(hass, mock_config_entry)
    mock_device.invoke_pin.side_effect = OpenhomeConnectionError("no route to host")

    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            OpenhomeService.INVOKE_PIN,
            {
                TargetKey.ENTITY_ID: ENTITY_ID,
                OpenhomeServiceArgument.PIN: 1,
            },
            blocking=True,
        )

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == translation_key
    assert mock_device.invoke_pin.await_count == await_count


async def test_media_player(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the media player is set up from the device state."""
    mock_device.track_info.return_value = TRACK_INFO

    await setup_media_player(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_becomes_unavailable_and_recovers(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a failed poll logs once, marks the device unavailable and recovers."""
    await setup_media_player(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING

    mock_device.room.side_effect = OpenhomeConnectionError("device unreachable")
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("device unreachable") == 1

    # A second consecutive failure must not log the same outage again.
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE
    assert caplog.text.count("device unreachable") == 1

    mock_device.room.side_effect = None
    await async_poll(hass)

    assert hass.states.get(ENTITY_ID).state == STATE_PLAYING


@pytest.mark.parametrize(
    ("in_standby", "transport_state", "expected_state"),
    [
        pytest.param(True, "Playing", STATE_OFF, id="standby"),
        pytest.param(False, "Paused", STATE_PAUSED, id="paused"),
        pytest.param(False, "Playing", STATE_PLAYING, id="playing"),
        pytest.param(False, "Buffering", STATE_PLAYING, id="buffering"),
        pytest.param(False, "Stopped", STATE_IDLE, id="stopped"),
        pytest.param(False, "Waiting", STATE_IDLE, id="waiting"),
        # An external source with no transport controls still counts as playing.
        pytest.param(False, "Unknown", STATE_PLAYING, id="external_source"),
    ],
)
async def test_state_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_device: MagicMock,
    in_standby: bool,
    transport_state: str,
    expected_state: str,
) -> None:
    """Test the device transport state maps onto the media player state."""
    mock_device.is_in_standby.return_value = in_standby
    mock_device.transport_state.return_value = transport_state

    await setup_media_player(hass, mock_config_entry)

    assert hass.states.get(ENTITY_ID).state == expected_state
