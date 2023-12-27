"""Test that we can upload images."""
import pathlib
import tempfile
from unittest.mock import patch

from aiohttp import ClientSession, ClientWebSocketResponse
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.websocket_api import const as ws_const
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from . import TEST_IMAGE

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_upload_image(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test we can upload an image."""
    now = dt_util.utcnow()
    freezer.move_to(now)

    with tempfile.TemporaryDirectory() as tempdir, patch.object(
        hass.config, "path", return_value=tempdir
    ):
        assert await async_setup_component(hass, "image_upload", {})
        ws_client: ClientWebSocketResponse = await hass_ws_client()
        client: ClientSession = await hass_client()

        with TEST_IMAGE.open("rb") as fp:
            res = await client.post("/api/image/upload", data={"file": fp})

        assert res.status == 200

        item = await res.json()

        assert item["content_type"] == "image/png"
        assert item["filesize"] == 38847
        assert item["name"] == "logo.png"
        assert item["uploaded_at"] == now.isoformat()

        tempdir = pathlib.Path(tempdir)
        item_folder: pathlib.Path = tempdir / item["id"]
        assert (item_folder / "original").read_bytes() == TEST_IMAGE.read_bytes()

        # fetch non-existing image
        res = await client.get("/api/image/serve/non-existing/256x256")
        assert res.status == 404

        # fetch invalid sizes
        for inv_size in ("256", "256x25A", "100x100", "25Ax256"):
            res = await client.get(f"/api/image/serve/{item['id']}/{inv_size}")
            assert res.status == 400

        # fetch resized version
        res = await client.get(f"/api/image/serve/{item['id']}/256x256")
        assert res.status == 200
        assert (item_folder / "256x256").is_file()

        # List item
        await ws_client.send_json({"id": 6, "type": "image/list"})
        msg = await ws_client.receive_json()

        assert msg["id"] == 6
        assert msg["type"] == ws_const.TYPE_RESULT
        assert msg["success"]
        assert msg["result"] == [item]

        # Delete item
        await ws_client.send_json(
            {"id": 7, "type": "image/delete", "image_id": item["id"]}
        )
        msg = await ws_client.receive_json()

        assert msg["id"] == 7
        assert msg["type"] == ws_const.TYPE_RESULT
        assert msg["success"]

        # Ensure removed from disk
        assert not item_folder.is_dir()
