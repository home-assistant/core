"""Test image_upload media source."""

import tempfile
from unittest.mock import patch

from aiohttp import ClientSession
import pytest

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import TEST_IMAGE

from tests.typing import ClientSessionGenerator


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def __upload_test_image(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> str:
    with (
        tempfile.TemporaryDirectory() as tempdir,
        patch.object(hass.config, "path", return_value=tempdir),
    ):
        assert await async_setup_component(hass, "image_upload", {})
        client: ClientSession = await hass_client()

        file = await hass.async_add_executor_job(TEST_IMAGE.open, "rb")
        res = await client.post("/api/image/upload", data={"file": file})
        hass.async_add_executor_job(file.close)

        assert res.status == 200
        item = await res.json()
        assert item["content_type"] == "image/png"
        assert item["filesize"] == 38847
        return item["id"]


async def test_browsing(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test browsing image media source."""
    image_id = await __upload_test_image(hass, hass_client)

    item = await media_source.async_browse_media(hass, "media-source://image_upload")

    assert item is not None
    assert item.title == "Image Upload"
    assert len(item.children) == 1
    assert item.children[0].media_content_type == "image/png"
    assert item.children[0].identifier == image_id
    assert item.children[0].thumbnail == f"/api/image/serve/{image_id}/256x256"

    with pytest.raises(
        media_source.BrowseError,
        match="Unknown item",
    ):
        await media_source.async_browse_media(
            hass, "media-source://image_upload/invalid_path"
        )


async def test_resolving(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test resolving."""
    image_id = await __upload_test_image(hass, hass_client)
    item = await media_source.async_resolve_media(
        hass, f"media-source://image_upload/{image_id}", None
    )
    assert item is not None
    assert item.url == f"/api/image/serve/{image_id}/original"
    assert item.mime_type == "image/png"

    invalid_id = "aabbccddeeff"
    with pytest.raises(
        media_source.Unresolvable,
        match=f"Could not resolve media item: {invalid_id}",
    ):
        await media_source.async_resolve_media(
            hass, f"media-source://image_upload/{invalid_id}", None
        )
