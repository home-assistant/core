"""Test media source HTTP."""

from unittest.mock import patch

import pytest
import yarl

from homeassistant.components import media_source
from homeassistant.components.media_player import (
    BrowseError,
    MediaClass,
    SearchMedia,
    SearchMediaQuery,
)
from homeassistant.components.media_source import const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import WebSocketGenerator


async def test_websocket_browse_media(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test browse media websocket."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    media = media_source.models.BrowseMediaSource(
        domain=media_source.DOMAIN,
        identifier="/media",
        title="Local Media",
        media_class=MediaClass.DIRECTORY,
        media_content_type="listing",
        can_play=False,
        can_expand=True,
    )

    with patch(
        "homeassistant.components.media_source.http.async_browse_media",
        return_value=media,
    ):
        await client.send_json(
            {
                "id": 1,
                "type": "media_source/browse_media",
            }
        )

        msg = await client.receive_json()

    assert msg["success"]
    assert msg["id"] == 1
    assert media.as_dict() == msg["result"]

    with patch(
        "homeassistant.components.media_source.http.async_browse_media",
        side_effect=BrowseError("test"),
    ):
        await client.send_json(
            {
                "id": 2,
                "type": "media_source/browse_media",
                "media_content_id": "invalid",
            }
        )

        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "browse_media_failed"
    assert msg["error"]["message"] == "test"


@pytest.mark.parametrize("filename", ["test.mp3", "Epic Sax Guy 10 Hours.mp4"])
async def test_websocket_resolve_media(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, filename
) -> None:
    """Test browse media websocket."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    media = media_source.models.PlayMedia(
        f"/media/local/{filename}",
        "audio/mpeg",
    )

    with patch(
        "homeassistant.components.media_source.http.async_resolve_media",
        return_value=media,
    ):
        await client.send_json(
            {
                "id": 1,
                "type": "media_source/resolve_media",
                "media_content_id": (
                    f"{const.URI_SCHEME}{media_source.DOMAIN}/local/{filename}"
                ),
            }
        )

        msg = await client.receive_json()

    assert msg["success"]
    assert msg["id"] == 1
    assert msg["result"]["mime_type"] == media.mime_type

    # Validate url is relative and signed.
    assert msg["result"]["url"][0] == "/"
    parsed = yarl.URL(msg["result"]["url"])
    assert parsed.path == media.url
    assert "authSig" in parsed.query

    with patch(
        "homeassistant.components.media_source.http.async_resolve_media",
        side_effect=media_source.Unresolvable("test"),
    ):
        await client.send_json(
            {
                "id": 2,
                "type": "media_source/resolve_media",
                "media_content_id": "invalid",
            }
        )

        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "resolve_media_failed"
    assert msg["error"]["message"] == "test"


async def test_websocket_search_media(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator
) -> None:
    """Test search media websocket."""
    assert await async_setup_component(hass, media_source.DOMAIN, {})
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    search_media = SearchMedia(
        result=[
            media_source.models.BrowseMediaSource(
                domain=media_source.DOMAIN,
                identifier="/media/test.mp3",
                title="test.mp3",
                media_class=MediaClass.MUSIC,
                media_content_type="audio/mpeg",
                can_play=True,
                can_expand=False,
            )
        ]
    )

    with patch(
        "homeassistant.components.media_source.http.async_search_media",
        return_value=search_media,
    ) as mock_search:
        await client.send_json(
            {
                "id": 1,
                "type": "media_source/search_media",
                "media_content_id": f"{const.URI_SCHEME}{media_source.DOMAIN}",
                "search_query": "test",
                "media_filter_classes": ["music"],
            }
        )

        msg = await client.receive_json()

    assert msg["success"]
    assert msg["id"] == 1
    assert msg["result"] == search_media.as_dict()

    # The query is built from the websocket message, coercing the filter classes
    query = mock_search.call_args[0][2]
    assert isinstance(query, SearchMediaQuery)
    assert query.search_query == "test"
    assert query.media_filter_classes == [MediaClass.MUSIC]

    with patch(
        "homeassistant.components.media_source.http.async_search_media",
        side_effect=BrowseError("test"),
    ):
        await client.send_json(
            {
                "id": 2,
                "type": "media_source/search_media",
                "media_content_id": "invalid",
                "search_query": "test",
            }
        )

        msg = await client.receive_json()

    assert not msg["success"]
    assert msg["error"]["code"] == "search_media_failed"
    assert msg["error"]["message"] == "test"
