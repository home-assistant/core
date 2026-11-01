"""Tests for the Camera Proxy camera platform."""

from collections.abc import AsyncGenerator
import io
from unittest.mock import AsyncMock, patch

from PIL import Image as PilImage
import pytest

from homeassistant.components.camera import Image, async_get_image
from homeassistant.components.proxy.camera import ProxyCamera
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.typing import ClientSessionGenerator

CROP_CONFIG = {
    "platform": "proxy",
    "entity_id": "camera.source",
    "name": "Cropped",
    "mode": "crop",
    "max_image_width": 400,
    "max_image_height": 225,
    "max_stream_width": 400,
    "max_stream_height": 225,
    "image_left": 550,
    "image_top": 90,
}


def _jpeg(width: int, height: int) -> Image:
    buffer = io.BytesIO()
    PilImage.new("RGB", (width, height)).save(buffer, "JPEG")
    return Image("image/jpeg", buffer.getvalue())


def _size(content: bytes) -> tuple[int, int]:
    return PilImage.open(io.BytesIO(content)).size


@pytest.fixture
async def setup_proxy(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Set up a cropping proxy camera with no delay between stream frames."""
    with patch.object(ProxyCamera, "_attr_frame_interval", 0):
        assert await async_setup_component(hass, "camera", {"camera": CROP_CONFIG})
        await hass.async_block_till_done()
        yield


@pytest.mark.usefixtures("setup_proxy")
async def test_crop_image_after_small_frame(hass: HomeAssistant) -> None:
    """Test a frame smaller than the crop area does not break later crops."""
    small = _jpeg(320, 180)
    with patch(
        "homeassistant.components.proxy.camera.async_get_image",
        AsyncMock(side_effect=[small, _jpeg(1536, 576)]),
    ):
        first = await async_get_image(hass, "camera.cropped")
        second = await async_get_image(hass, "camera.cropped")

    assert first.content == small.content
    assert _size(second.content) == (400, 225)


@pytest.mark.usefixtures("setup_proxy")
async def test_crop_stream_after_small_frame(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test a small frame does not break the cropped MJPEG stream."""
    client = await hass_client()
    with patch(
        "homeassistant.components.proxy.camera.async_get_image",
        AsyncMock(side_effect=[_jpeg(320, 180), _jpeg(1536, 576), None]),
    ):
        response = await client.get("/api/camera_proxy_stream/camera.cropped")
        body = await response.read()

    assert response.status == 200
    frames = [
        part.split(b"\r\n\r\n", 1)[1].rstrip(b"\r\n")
        for part in body.split(b"--frameboundary\r\n")
        if b"\r\n\r\n" in part
    ]
    assert _size(frames[-1]) == (400, 225)
