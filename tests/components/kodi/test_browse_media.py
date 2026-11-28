"""Tests for the Kodi media browser."""

from unittest.mock import AsyncMock, MagicMock

from pykodi import ProtocolError
import pytest

from homeassistant.components.kodi.browse_media import get_media_info
from homeassistant.components.media_player import MediaType

CHANNELS = {
    "channels": [
        {
            "channelid": 917,
            "label": "Das Erste HD",
            "thumbnail": "image://pvrchannel_tv%40das_erste/",
        },
        {
            "channelid": 902,
            "label": "ZDF HD",
            "thumbnail": "image://pvrchannel_tv%40zdf/",
        },
        {
            "channelid": 850,
            "label": "3sat HD",
        },
    ]
}


def create_media_library() -> MagicMock:
    """Return a Kodi library that answers with the TV channels above."""
    library = MagicMock()
    library.get_channels = AsyncMock(return_value=CHANNELS)
    library.thumbnail_url = MagicMock(
        side_effect=lambda thumbnail: (
            f"http://1.1.1.1:8080/image/{thumbnail}" if thumbnail else None
        )
    )
    return library


async def test_channel_folder_lists_the_channels() -> None:
    """The folder itself is listed and has no thumbnail of its own."""
    library = create_media_library()

    thumbnail, title, media = await get_media_info(library, "", MediaType.CHANNEL)

    assert title == "Channels"
    assert media == CHANNELS["channels"]
    assert thumbnail is None


async def test_channel_asked_for_by_id_carries_its_thumbnail() -> None:
    """A single channel returns the image the media player proxy serves.

    An external client fetches a browse thumbnail over
    /api/media_player_proxy/<entity>/browse_media/channel/<id>, which asks the
    integration for the image by id. Without this the view answers 404.
    """
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "902", MediaType.CHANNEL)

    assert thumbnail == "http://1.1.1.1:8080/image/image://pvrchannel_tv%40zdf/"


async def test_channel_without_a_thumbnail_has_no_picture() -> None:
    """Kodi does not promise a thumbnail for every channel."""
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "850", MediaType.CHANNEL)

    assert thumbnail is None


async def test_channel_no_longer_in_the_group_has_no_thumbnail() -> None:
    """An id that is not in the list leaves the thumbnail unset."""
    library = create_media_library()

    thumbnail, _, _ = await get_media_info(library, "123", MediaType.CHANNEL)

    assert thumbnail is None


async def test_channel_listing_asks_for_the_epg() -> None:
    """The listing needs what it shows: the current broadcast."""
    library = create_media_library()

    await get_media_info(library, "", MediaType.CHANNEL)

    assert library.get_channels.call_args.kwargs["properties"] == [
        "thumbnail",
        "channeltype",
        "channel",
        "broadcastnow",
    ]


async def test_single_channel_asks_for_no_more_than_the_thumbnail() -> None:
    """One image needs no EPG for a hundred and fifty channels."""
    library = create_media_library()

    await get_media_info(library, "902", MediaType.CHANNEL)

    assert library.get_channels.call_args.kwargs["properties"] == ["thumbnail"]


async def test_season_asked_for_by_bare_season_id() -> None:
    """A bare numeric Kodi seasonid resolves its show and season number."""
    library = create_media_library()
    episodes = [{"episodeid": 101, "seasonid": 25, "tvshowid": 4, "label": "Episode 1"}]
    library.get_season_details = AsyncMock(
        side_effect=[
            {"seasondetails": {"tvshowid": 4, "season": 2}},
            {
                "seasondetails": {
                    "label": "Season 2",
                    "art": {"poster": "image://season_2/"},
                }
            },
        ]
    )
    library.get_episodes = AsyncMock(return_value={"episodes": episodes})

    thumbnail, title, media = await get_media_info(library, "25", MediaType.SEASON)

    library.get_episodes.assert_awaited_once_with(
        tv_show_id=4,
        season_id=2,
        properties=["thumbnail", "tvshowid", "seasonid", "art"],
    )
    assert thumbnail == "http://1.1.1.1:8080/image/image://season_2/"
    assert title == "Season 2"
    assert media == episodes


@pytest.mark.parametrize("search_id", ["", "invalid", "²", "4/abc", "4/-1", "4/²"])
async def test_malformed_season_id_returns_not_found(search_id: str) -> None:
    """Malformed season IDs return empty media instead of raising ValueError."""
    library = create_media_library()
    library.get_episodes = AsyncMock()
    library.get_season_details = AsyncMock()

    thumbnail, title, media = await get_media_info(library, search_id, MediaType.SEASON)

    assert (thumbnail, title, media) == (None, None, None)
    library.get_episodes.assert_not_awaited()
    library.get_season_details.assert_not_awaited()


async def test_unknown_bare_season_id_returns_not_found() -> None:
    """Kodi JSON-RPC -32602 Invalid params on an unknown seasonid maps to not found."""
    library = create_media_library()
    library.get_season_details = AsyncMock(
        side_effect=ProtocolError(-32602, "Invalid params.")
    )
    library.get_episodes = AsyncMock()

    thumbnail, title, media = await get_media_info(library, "999", MediaType.SEASON)

    assert (thumbnail, title, media) == (None, None, None)
    library.get_episodes.assert_not_awaited()


async def test_unexpected_protocol_error_on_season_propagates() -> None:
    """Protocol errors other than -32602 are not swallowed."""
    library = create_media_library()
    library.get_season_details = AsyncMock(
        side_effect=ProtocolError(-32603, "Internal error.")
    )

    with pytest.raises(ProtocolError):
        await get_media_info(library, "999", MediaType.SEASON)


async def test_unknown_composite_season_id_returns_not_found() -> None:
    """Kodi JSON-RPC -32602 Invalid params on get_episodes maps to not found."""
    library = create_media_library()
    library.get_episodes = AsyncMock(
        side_effect=ProtocolError(-32602, "Invalid params.")
    )
    library.get_season_details = AsyncMock()

    thumbnail, title, media = await get_media_info(library, "4/99", MediaType.SEASON)

    assert (thumbnail, title, media) == (None, None, None)
    library.get_season_details.assert_not_awaited()


async def test_unexpected_protocol_error_on_season_episodes_propagates() -> None:
    """Protocol errors other than -32602 from get_episodes are not swallowed."""
    library = create_media_library()
    library.get_episodes = AsyncMock(
        side_effect=ProtocolError(-32603, "Internal error.")
    )

    with pytest.raises(ProtocolError):
        await get_media_info(library, "4/99", MediaType.SEASON)
