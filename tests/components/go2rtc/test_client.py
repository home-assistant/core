"""Test go2rtc client."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.camera import async_get_image
from homeassistant.components.go2rtc import HomeAssistant
from homeassistant.components.go2rtc.const import DOMAIN
from homeassistant.exceptions import HomeAssistantError

from . import MockCamera

from tests.common import load_fixture_bytes


@pytest.mark.usefixtures("init_integration")
async def test_async_get_image(
    hass: HomeAssistant,
    init_test_integration: MockCamera,
    rest_client: AsyncMock,
) -> None:
    """Test getting snapshot from go2rtc."""
    camera = init_test_integration
    assert camera.go2rtc_client, "Camera should have go2rtc client"

    image_bytes = load_fixture_bytes("snapshot.jpg", DOMAIN)

    rest_client.get_jpeg_snapshot.return_value = image_bytes
    assert await camera.go2rtc_client.async_get_image(camera) == image_bytes

    image = await async_get_image(hass, camera.entity_id)
    assert image.content == image_bytes

    camera.set_stream_source("invalid://not_supported")

    with pytest.raises(
        HomeAssistantError, match="Stream source is not supported by go2rtc"
    ):
        await async_get_image(hass, camera.entity_id)

    assert camera.go2rtc_client is None, (
        "Camera should not have go2rtc client after changing to a not supported stream"
    )
