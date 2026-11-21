"""Test the ONVIF camera platform."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.camera import async_get_stream_source
from homeassistant.core import HomeAssistant

from . import PASSWORD, USERNAME, setup_onvif_integration

ENTITY_ID = "camera.testcamera_profile1"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_stream_uri_retried_after_failure(hass: HomeAssistant) -> None:
    """Test the stream URI is fetched again after a failed attempt."""
    _, _, device = await setup_onvif_integration(hass)
    device.username = USERNAME
    device.password = PASSWORD
    device.async_get_stream_uri = AsyncMock(
        side_effect=[TimeoutError, "rtsp://1.2.3.4/stream"]
    )

    with pytest.raises(TimeoutError):
        await async_get_stream_source(hass, ENTITY_ID)

    assert (
        await async_get_stream_source(hass, ENTITY_ID)
        == f"rtsp://{USERNAME}:{PASSWORD}@1.2.3.4/stream"
    )
    assert device.async_get_stream_uri.await_count == 2
