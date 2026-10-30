"""Test image media source."""

import pytest

from homeassistant.components import media_source
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


async def test_browsing(hass: HomeAssistant, mock_image_platform) -> None:
    """Test browsing image media source."""
    item = await media_source.async_browse_media(hass, "media-source://image")
    assert item is not None
    assert item.title == "Image"
    assert len(item.children) == 1
    assert item.children[0].media_content_type == "image/jpeg"


async def test_resolving(hass: HomeAssistant, mock_image_platform) -> None:
    """Test resolving."""
    item = await media_source.async_resolve_media(
        hass, "media-source://image/image.test", None
    )
    assert item is not None
    assert item.url == "/api/image_proxy_stream/image.test"
    assert item.mime_type == "image/jpeg"


async def test_resolving_non_existing_camera(
    hass: HomeAssistant, mock_image_platform
) -> None:
    """Test resolving."""
    with pytest.raises(
        media_source.Unresolvable,
        match="Could not resolve media item: image.non_existing",
    ):
        await media_source.async_resolve_media(
            hass, "media-source://image/image.non_existing", None
        )


@pytest.mark.usefixtures("mock_image_platform")
async def test_get_media_image(hass: HomeAssistant) -> None:
    """Test getting the image of an image entity."""
    assert await media_source.async_get_media_image(
        hass, "media-source://image/image.test"
    ) == media_source.MediaImage(b"Test", "image/jpeg")


@pytest.mark.usefixtures("mock_image_platform")
async def test_get_media_image_non_existing_image(hass: HomeAssistant) -> None:
    """Test getting the image of a non existing image entity."""
    with pytest.raises(
        media_source.Unresolvable,
        match="Could not resolve media item: image.non_existing",
    ):
        await media_source.async_get_media_image(
            hass, "media-source://image/image.non_existing"
        )
