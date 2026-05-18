"""Test the base functions of the media player."""

from http import HTTPStatus
from unittest.mock import patch

import aiohttp
import pytest
import voluptuous as vol

from homeassistant.components import media_player
from homeassistant.components.media_player import (
    ATTR_MEDIA_CONTENT_ID,
    ATTR_MEDIA_CONTENT_TYPE,
    ATTR_MEDIA_FILTER_CLASSES,
    ATTR_MEDIA_SEARCH_QUERY,
    BrowseMedia,
    MediaClass,
    MediaPlayerEnqueue,
    MediaPlayerEntity,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_player.const import (
    SERVICE_BROWSE_MEDIA,
    SERVICE_SEARCH_MEDIA,
)
from homeassistant.components.websocket_api import TYPE_RESULT
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockEntityPlatform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.mark.parametrize(
    "property_suffix",
    [
        "play",
        "pause",
        "stop",
        "seek",
        "volume_set",
        "volume_mute",
        "previous_track",
        "next_track",
        "play_media",
        "select_source",
        "select_sound_mode",
        "clear_playlist",
        "shuffle_set",
        "grouping",
    ],
)
def test_support_properties(hass: HomeAssistant, property_suffix: str) -> None:
    """Test support_*** properties explicitly."""

    all_features = media_player.MediaPlayerEntityFeature(653887)
    feature = media_player.MediaPlayerEntityFeature[property_suffix.upper()]

    entity1 = MediaPlayerEntity()
    entity1.hass = hass
    entity1.platform = MockEntityPlatform(hass)
    entity1._attr_supported_features = media_player.MediaPlayerEntityFeature(0)
    entity2 = MediaPlayerEntity()
    entity2.hass = hass
    entity2.platform = MockEntityPlatform(hass)
    entity2._attr_supported_features = all_features
    entity3 = MediaPlayerEntity()
    entity3.hass = hass
    entity3.platform = MockEntityPlatform(hass)
    entity3._attr_supported_features = feature
    entity4 = MediaPlayerEntity()
    entity4.hass = hass
    entity4.platform = MockEntityPlatform(hass)
    entity4._attr_supported_features = media_player.MediaPlayerEntityFeature(
        all_features - feature
    )

    assert getattr(entity1, f"support_{property_suffix}") is False
    assert getattr(entity2, f"support_{property_suffix}") is True
    assert getattr(entity3, f"support_{property_suffix}") is True
    assert getattr(entity4, f"support_{property_suffix}") is False


async def test_get_image_http(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test get image via http command."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.bedroom")
    assert "entity_picture_local" not in state.attributes

    client = await hass_client_no_auth()

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity.async_get_media_image",
        return_value=(b"image", "image/jpeg"),
    ):
        resp = await client.get(state.attributes["entity_picture"])
        content = await resp.read()

    assert content == b"image"


async def test_get_image_http_remote(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Test get image url via http command."""
    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "media_image_remotely_accessible",
        return_value=True,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()

        state = hass.states.get("media_player.bedroom")
        assert "entity_picture_local" in state.attributes

        client = await hass_client_no_auth()

        with patch(
            "homeassistant.components.media_player.MediaPlayerEntity."
            "async_get_media_image",
            return_value=(b"image", "image/jpeg"),
        ):
            resp = await client.get(state.attributes["entity_picture_local"])
            content = await resp.read()

        assert content == b"image"


async def test_get_image_http_log_credentials_redacted(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test credentials are redacted when logging url when fetching image."""
    url = "http://vi:pass@example.com/default.jpg"
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_image_url",
        url,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()

        state = hass.states.get("media_player.bedroom")
        assert "entity_picture_local" not in state.attributes

        aioclient_mock.get(url, exc=TimeoutError())

        client = await hass_client_no_auth()

        resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert f"Error retrieving proxied image from {url}" not in caplog.text
    assert (
        "Error retrieving proxied image from "
        f"{url.replace('pass', 'xxxxxxxx').replace('vi', 'xxxx')}"
    ) in caplog.text


async def test_get_image_http_truncated_log_credentials_redacted(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Credentials must be redacted in the truncated-response warning too.

    The 'Discarding truncated image response' warning is a second log site
    that carries the upstream URL. It needs the same credential redaction
    the 'Error retrieving proxied image' path already has.
    """
    url = "http://vi:pass@example.com/truncated.jpg"
    truncated = b"\xff\xd8\xff\xe0" + b"\x00" * 200  # JPEG SOI without EOI
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_image_url",
        url,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()
        state = hass.states.get("media_player.bedroom")
        aioclient_mock.get(
            url, content=truncated, headers={"Content-Type": "image/jpeg"}
        )
        client = await hass_client_no_auth()
        resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert f"Discarding truncated image response from {url}" not in caplog.text
    redacted = url.replace("pass", "xxxxxxxx").replace("vi", "xxxx")
    assert f"Discarding truncated image response from {redacted}" in caplog.text


@pytest.mark.parametrize(
    "fetch_exception",
    [
        pytest.param(TimeoutError(), id="timeout"),
        pytest.param(
            aiohttp.ClientPayloadError("incomplete chunked read"),
            id="client_payload_error",
        ),
        pytest.param(
            aiohttp.ClientConnectionError("connection reset"),
            id="client_connection_error",
        ),
    ],
)
async def test_get_image_http_aiohttp_failure_returns_500(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    fetch_exception: BaseException,
) -> None:
    """Test aiohttp errors during image fetch are caught and surfaced as 500.

    Both TimeoutError and aiohttp.ClientError subclasses are suppressed in
    async_fetch_image so the failure falls into the existing "Error
    retrieving proxied image" path rather than propagating. The ClientError
    case is forward-compat for once aiohttp raises ClientPayloadError on a
    truncated chunked stream rather than swallowing it as clean EOF.
    """
    url = "http://example.com/image.jpg"
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_image_url",
        url,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()

        state = hass.states.get("media_player.bedroom")
        aioclient_mock.get(url, exc=fetch_exception)
        client = await hass_client_no_auth()
        resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert f"Error retrieving proxied image from {url}" in caplog.text


@pytest.mark.parametrize(
    ("response_body", "response_headers", "expect_status", "expect_log_fragment"),
    [
        pytest.param(
            b"\xff\xd8\xff\xe0" + b"\x00" * 1024,
            {"Content-Type": "image/jpeg"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Discarding truncated image response",
            id="jpeg_missing_eoi",
        ),
        pytest.param(
            b"\x89PNG\r\n\x1a\n" + b"\x00" * 1024,
            {"Content-Type": "image/png"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Discarding truncated image response",
            id="png_missing_iend",
        ),
        pytest.param(
            b"hello-world",
            {"Content-Type": "image/jpeg", "Content-Length": "9999"},
            HTTPStatus.INTERNAL_SERVER_ERROR,
            "Discarding truncated image response",
            id="content_length_mismatch",
        ),
        pytest.param(
            b"\xff\xd8\xff\xe0" + b"\x00" * 1024 + b"\xff\xd9",
            {"Content-Type": "image/jpeg"},
            HTTPStatus.OK,
            None,
            id="jpeg_complete_with_eoi",
        ),
    ],
)
async def test_get_image_http_truncated_response(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    caplog: pytest.LogCaptureFixture,
    response_body: bytes,
    response_headers: dict[str, str],
    expect_status: HTTPStatus,
    expect_log_fragment: str | None,
) -> None:
    """Test silently-truncated image responses are discarded, not cached.

    aiohttp can return partial bytes without raising when an upstream
    chunked stream is reset mid-body, or when a Content-Length is
    advertised but the connection closes early. async_fetch_image must
    detect this and avoid caching the partial body as if it were the
    full image (which would otherwise persist for the cache lifetime).
    """
    url = "http://example.com/truncated.jpg"
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_image_url",
        url,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()

        state = hass.states.get("media_player.bedroom")
        aioclient_mock.get(url, content=response_body, headers=response_headers)
        client = await hass_client_no_auth()
        resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == expect_status
    if expect_log_fragment is not None:
        assert expect_log_fragment in caplog.text
    else:
        assert "Discarding truncated image response" not in caplog.text
        body = await resp.read()
        assert body == response_body


async def test_get_image_http_truncated_fetch_is_not_cached(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """A truncated fetch must not be cached so a later retry can succeed.

    Before this behavior change, async_fetch_image returning (None, None)
    was cached the same as a successful response, which made any failure
    permanent for the cache lifetime. The truncation guard would have
    turned the original half-rendered image symptom into a fully broken
    one. The cache write is now skipped on failure so the next request
    retries from the source.
    """
    url = "http://example.com/recoverable.jpg"
    truncated = b"\xff\xd8\xff\xe0" + b"\x00" * 1024
    complete = b"\xff\xd8\xff\xe0" + b"\x00" * 1024 + b"\xff\xd9"
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.media_image_url",
        url,
    ):
        await async_setup_component(
            hass, "media_player", {"media_player": {"platform": "demo"}}
        )
        await hass.async_block_till_done()
        state = hass.states.get("media_player.bedroom")
        client = await hass_client_no_auth()

        # First request: upstream returns a truncated JPEG.
        aioclient_mock.get(
            url, content=truncated, headers={"Content-Type": "image/jpeg"}
        )
        resp1 = await client.get(state.attributes["entity_picture"])
        assert resp1.status == HTTPStatus.INTERNAL_SERVER_ERROR

        # Second request, same URL: upstream now returns the complete JPEG.
        # If the failure had been cached, this would still 500.
        aioclient_mock.clear_requests()
        aioclient_mock.get(
            url, content=complete, headers={"Content-Type": "image/jpeg"}
        )
        resp2 = await client.get(state.attributes["entity_picture"])
        assert resp2.status == HTTPStatus.OK
        assert await resp2.read() == complete


async def test_get_async_get_browse_image(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test get browse image."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_comp = hass.data.get("entity_components", {}).get("media_player")
    assert entity_comp

    player = entity_comp.get_entity("media_player.bedroom")
    assert player

    client = await hass_client_no_auth()

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "async_get_browse_image",
        return_value=(b"image", "image/jpeg"),
    ):
        url = player.get_browse_image_url("album", "abcd")
        resp = await client.get(url)
        content = await resp.read()

    assert content == b"image"


async def test_media_browse(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test browsing media."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.demo.media_player.DemoBrowsePlayer.async_browse_media",
        return_value=BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="mock-id",
            media_content_type="mock-type",
            title="Mock Title",
            can_play=False,
            can_expand=True,
        ),
    ) as mock_browse_media:
        await client.send_json(
            {
                "id": 5,
                "type": "media_player/browse_media",
                "entity_id": "media_player.browse",
                "media_content_type": "album",
                "media_content_id": "abcd",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {
        "title": "Mock Title",
        "media_class": "directory",
        "media_content_type": "mock-type",
        "media_content_id": "mock-id",
        "can_play": False,
        "can_expand": True,
        "can_search": False,
        "children_media_class": None,
        "thumbnail": None,
        "not_shown": 0,
        "children": [],
    }
    assert mock_browse_media.mock_calls[0][1] == ("album", "abcd")

    with patch(
        "homeassistant.components.demo.media_player.DemoBrowsePlayer.async_browse_media",
        return_value={"bla": "yo"},
    ):
        await client.send_json(
            {
                "id": 6,
                "type": "media_player/browse_media",
                "entity_id": "media_player.browse",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"bla": "yo"}


async def test_media_browse_service(hass: HomeAssistant) -> None:
    """Test browsing media using service call."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.demo.media_player.DemoBrowsePlayer.async_browse_media",
        return_value=BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="mock-id",
            media_content_type="mock-type",
            title="Mock Title",
            can_play=False,
            can_expand=True,
            children=[
                BrowseMedia(
                    media_class=MediaClass.ALBUM,
                    media_content_id="album1 content id",
                    media_content_type="album",
                    title="Album 1",
                    can_play=True,
                    can_expand=True,
                ),
                BrowseMedia(
                    media_class=MediaClass.ALBUM,
                    media_content_id="album2 content id",
                    media_content_type="album",
                    title="Album 2",
                    can_play=True,
                    can_expand=True,
                ),
            ],
        ),
    ) as mock_browse_media:
        result = await hass.services.async_call(
            "media_player",
            SERVICE_BROWSE_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.browse",
                ATTR_MEDIA_CONTENT_TYPE: "album",
                ATTR_MEDIA_CONTENT_ID: "title=Album*",
            },
            blocking=True,
            return_response=True,
        )

        mock_browse_media.assert_called_with(
            media_content_type="album", media_content_id="title=Album*"
        )
        browse_res: BrowseMedia = result["media_player.browse"]
        assert browse_res.title == "Mock Title"
        assert browse_res.media_class == "directory"
        assert browse_res.media_content_type == "mock-type"
        assert browse_res.media_content_id == "mock-id"
        assert browse_res.can_play is False
        assert browse_res.can_expand is True
        assert len(browse_res.children) == 2
        assert browse_res.children[0].title == "Album 1"
        assert browse_res.children[0].media_class == "album"
        assert browse_res.children[0].media_content_id == "album1 content id"
        assert browse_res.children[0].media_content_type == "album"
        assert browse_res.children[1].title == "Album 2"
        assert browse_res.children[1].media_class == "album"
        assert browse_res.children[1].media_content_id == "album2 content id"
        assert browse_res.children[1].media_content_type == "album"


async def test_media_search(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test browsing media."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.demo.media_player.DemoSearchPlayer.async_search_media",
        return_value=SearchMedia(
            result=[
                BrowseMedia(
                    media_class=MediaClass.DIRECTORY,
                    media_content_id="mock-id",
                    media_content_type="mock-type",
                    title="Mock Title",
                    can_play=False,
                    can_expand=True,
                )
            ]
        ),
    ) as mock_search_media:
        await client.send_json(
            {
                "id": 7,
                "type": "media_player/search_media",
                "entity_id": "media_player.search",
                "media_content_type": "album",
                "media_content_id": "abcd",
                "search_query": "query",
                "media_filter_classes": ["album"],
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 7
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["result"] == [
        {
            "title": "Mock Title",
            "media_class": "directory",
            "media_content_type": "mock-type",
            "media_content_id": "mock-id",
            "children_media_class": None,
            "can_play": False,
            "can_expand": True,
            "can_search": False,
            "thumbnail": None,
            "not_shown": 0,
            "children": [],
        }
    ]
    assert mock_search_media.mock_calls[0].kwargs["query"] == SearchMediaQuery(
        search_query="query",
        media_content_type="album",
        media_content_id="abcd",
        media_filter_classes={MediaClass.ALBUM},
    )


async def test_media_search_service(hass: HomeAssistant) -> None:
    """Test browsing media."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()
    expected = [
        BrowseMedia(
            media_class=MediaClass.DIRECTORY,
            media_content_id="mock-id",
            media_content_type="mock-type",
            title="Mock Title",
            can_play=False,
            can_expand=True,
            children=[],
        )
    ]

    with patch(
        "homeassistant.components.demo.media_player.DemoSearchPlayer.async_search_media",
        return_value=SearchMedia(result=expected),
    ) as mock_search_media:
        result = await hass.services.async_call(
            "media_player",
            SERVICE_SEARCH_MEDIA,
            {
                ATTR_ENTITY_ID: "media_player.search",
                ATTR_MEDIA_CONTENT_TYPE: "album",
                ATTR_MEDIA_CONTENT_ID: "title=Album*",
                ATTR_MEDIA_SEARCH_QUERY: "query",
                ATTR_MEDIA_FILTER_CLASSES: ["album"],
            },
            blocking=True,
            return_response=True,
        )

    search_res: SearchMedia = result["media_player.search"]
    assert search_res.version == 1
    assert search_res.result == expected
    assert mock_search_media.mock_calls[0].kwargs["query"] == SearchMediaQuery(
        search_query="query",
        media_content_type="album",
        media_content_id="title=Album*",
        media_filter_classes={MediaClass.ALBUM},
    )


async def test_group_members_available_when_off(hass: HomeAssistant) -> None:
    """Test that group_members are still available when media_player is off."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    await hass.services.async_call(
        "media_player",
        "turn_off",
        {ATTR_ENTITY_ID: "media_player.group"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.group")
    assert state.state == STATE_OFF
    assert "group_members" in state.attributes


@pytest.mark.parametrize(
    ("input", "expected"),
    [
        (True, MediaPlayerEnqueue.ADD),
        (False, MediaPlayerEnqueue.PLAY),
        ("play", MediaPlayerEnqueue.PLAY),
        ("next", MediaPlayerEnqueue.NEXT),
        ("add", MediaPlayerEnqueue.ADD),
        ("replace", MediaPlayerEnqueue.REPLACE),
    ],
)
async def test_enqueue_rewrite(hass: HomeAssistant, input, expected) -> None:
    """Test that group_members are still available when media_player is off."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    # Fake group support for DemoYoutubePlayer
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.play_media",
    ) as mock_play_media:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.bedroom",
                "media_content_type": "music",
                "media_content_id": "1234",
                "enqueue": input,
            },
            blocking=True,
        )

    assert len(mock_play_media.mock_calls) == 1
    assert mock_play_media.mock_calls[0][2]["enqueue"] == expected


async def test_enqueue_alert_exclusive(hass: HomeAssistant) -> None:
    """Test that alert and enqueue cannot be used together."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.bedroom",
                "media_content_type": "music",
                "media_content_id": "1234",
                "enqueue": "play",
                "announce": True,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "media_content_id",
    [
        "a/b c/d+e%2Fg{}",
        "a/b c/d+e%2D",
        "a/b c/d+e%2E",
        "2012-06%20Pool%20party%20%2F%20BBQ",
    ],
)
async def test_get_async_get_browse_image_quoting(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    media_content_id: str,
) -> None:
    """Test get browse image using media_content_id with special characters.

    async_get_browse_image() should get called with the same string that is
    passed into get_browse_image_url().
    """
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    entity_comp = hass.data.get("entity_components", {}).get("media_player")
    assert entity_comp

    player = entity_comp.get_entity("media_player.bedroom")
    assert player

    client = await hass_client_no_auth()

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "async_get_browse_image",
    ) as mock_browse_image:
        url = player.get_browse_image_url("album", media_content_id)
        await client.get(url)
        mock_browse_image.assert_called_with("album", media_content_id, None)


async def test_play_media_via_selector(hass: HomeAssistant) -> None:
    """Test that play_media data under 'media' is remapped to top level keys for backward compatibility."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    # Fake group support for DemoYoutubePlayer
    with patch(
        "homeassistant.components.demo.media_player.DemoYoutubePlayer.play_media",
    ) as mock_play_media:
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.bedroom",
                "media": {
                    "media_content_type": "music",
                    "media_content_id": "1234",
                },
            },
            blocking=True,
        )
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "entity_id": "media_player.bedroom",
                "media_content_type": "music",
                "media_content_id": "1234",
            },
            blocking=True,
        )

    assert len(mock_play_media.mock_calls) == 2
    assert mock_play_media.mock_calls[0].args == mock_play_media.mock_calls[1].args

    with pytest.raises(vol.Invalid, match="Play media cannot contain 'media'"):
        await hass.services.async_call(
            "media_player",
            "play_media",
            {
                "media_content_id": "1234",
                "entity_id": "media_player.bedroom",
                "media": {
                    "media_content_type": "music",
                    "media_content_id": "1234",
                },
            },
            blocking=True,
        )
