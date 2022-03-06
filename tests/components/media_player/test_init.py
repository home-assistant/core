"""Test the base functions of the media player."""
import asyncio
import base64
from http import HTTPStatus
from unittest.mock import patch

from homeassistant.components import media_player
from homeassistant.components.media_player.browse_media import BrowseMedia
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF
from homeassistant.setup import async_setup_component


async def test_get_image(hass, hass_ws_client, caplog):
    """Test get image via WS command."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "async_get_media_image",
        return_value=(b"image", "image/jpeg"),
    ):
        await client.send_json(
            {
                "id": 5,
                "type": "media_player_thumbnail",
                "entity_id": "media_player.bedroom",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 5
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"]["content_type"] == "image/jpeg"
    assert msg["result"]["content"] == base64.b64encode(b"image").decode("utf-8")

    assert "media_player_thumbnail is deprecated" in caplog.text


async def test_get_image_http(hass, hass_client_no_auth):
    """Test get image via http command."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.bedroom")
    assert "entity_picture_local" not in state.attributes

    client = await hass_client_no_auth()

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "async_get_media_image",
        return_value=(b"image", "image/jpeg"),
    ):
        resp = await client.get(state.attributes["entity_picture"])
        content = await resp.read()

    assert content == b"image"


async def test_get_image_http_remote(hass, hass_client_no_auth):
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
    hass, hass_client_no_auth, aioclient_mock, caplog
):
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

        aioclient_mock.get(url, exc=asyncio.TimeoutError())

        client = await hass_client_no_auth()

        resp = await client.get(state.attributes["entity_picture"])

    assert resp.status == HTTPStatus.INTERNAL_SERVER_ERROR
    assert f"Error retrieving proxied image from {url}" not in caplog.text
    assert (
        "Error retrieving proxied image from "
        f"{url.replace('pass', 'xxxxxxxx').replace('vi', 'xxxx')}"
    ) in caplog.text


async def test_get_async_get_browse_image(hass, hass_client_no_auth, hass_ws_client):
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


async def test_media_browse(hass, hass_ws_client):
    """Test browsing media."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)

    with patch(
        "homeassistant.components.demo.media_player.YOUTUBE_PLAYER_SUPPORT",
        media_player.SUPPORT_BROWSE_MEDIA,
    ), patch(
        "homeassistant.components.media_player.MediaPlayerEntity.async_browse_media",
        return_value=BrowseMedia(
            media_class=media_player.MEDIA_CLASS_DIRECTORY,
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
                "entity_id": "media_player.bedroom",
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
        "children_media_class": None,
        "thumbnail": None,
        "not_shown": 0,
        "children": [],
    }
    assert mock_browse_media.mock_calls[0][1] == ("album", "abcd")

    with patch(
        "homeassistant.components.demo.media_player.YOUTUBE_PLAYER_SUPPORT",
        media_player.SUPPORT_BROWSE_MEDIA,
    ), patch(
        "homeassistant.components.media_player.MediaPlayerEntity.async_browse_media",
        return_value={"bla": "yo"},
    ):
        await client.send_json(
            {
                "id": 6,
                "type": "media_player/browse_media",
                "entity_id": "media_player.bedroom",
            }
        )

        msg = await client.receive_json()

    assert msg["id"] == 6
    assert msg["type"] == TYPE_RESULT
    assert msg["success"]
    assert msg["result"] == {"bla": "yo"}


async def test_group_members_available_when_off(hass):
    """Test that group_members are still available when media_player is off."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    # Fake group support for DemoYoutubePlayer
    with patch(
        "homeassistant.components.demo.media_player.YOUTUBE_PLAYER_SUPPORT",
        media_player.SUPPORT_GROUPING | media_player.SUPPORT_TURN_OFF,
    ):
        await hass.services.async_call(
            "media_player",
            "turn_off",
            {ATTR_ENTITY_ID: "media_player.bedroom"},
            blocking=True,
        )

    state = hass.states.get("media_player.bedroom")
    assert state.state == STATE_OFF
    assert "group_members" in state.attributes
