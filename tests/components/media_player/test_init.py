"""Test the base functions of the media player."""
import base64

from homeassistant.components import media_player
from homeassistant.components.websocket_api.const import TYPE_RESULT
from homeassistant.setup import async_setup_component

from tests.async_mock import patch


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


async def test_get_image_http(hass, aiohttp_client):
    """Test get image via http command."""
    await async_setup_component(
        hass, "media_player", {"media_player": {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    state = hass.states.get("media_player.bedroom")
    assert "entity_picture_local" not in state.attributes

    client = await aiohttp_client(hass.http.app)

    with patch(
        "homeassistant.components.media_player.MediaPlayerEntity."
        "async_get_media_image",
        return_value=(b"image", "image/jpeg"),
    ):
        resp = await client.get(state.attributes["entity_picture"])
        content = await resp.read()

    assert content == b"image"


async def test_get_image_http_remote(hass, aiohttp_client):
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

        client = await aiohttp_client(hass.http.app)

        with patch(
            "homeassistant.components.media_player.MediaPlayerEntity."
            "async_get_media_image",
            return_value=(b"image", "image/jpeg"),
        ):
            resp = await client.get(state.attributes["entity_picture_local"])
            content = await resp.read()

        assert content == b"image"


def test_deprecated_base_class(caplog):
    """Test deprecated base class."""

    class CustomMediaPlayer(media_player.MediaPlayerDevice):
        pass

    CustomMediaPlayer()
    assert "MediaPlayerDevice is deprecated, modify CustomMediaPlayer" in caplog.text
