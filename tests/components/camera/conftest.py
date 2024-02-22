"""Test helpers for camera."""
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera.const import StreamType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import WEBRTC_ANSWER


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
async def camera_only() -> None:
    """Enable only the camera platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.CAMERA],
    ):
        yield


@pytest.fixture(name="mock_camera")
async def mock_camera_fixture(hass):
    """Initialize a demo camera platform."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.demo.camera.Path.read_bytes",
        return_value=b"Test",
    ):
        yield


@pytest.fixture(name="mock_camera_hls")
async def mock_camera_hls_fixture(mock_camera):
    """Initialize a demo camera platform with HLS."""
    with patch(
        "homeassistant.components.camera.Camera.frontend_stream_type",
        new_callable=PropertyMock(return_value=StreamType.HLS),
    ):
        yield


@pytest.fixture(name="mock_camera_web_rtc")
async def mock_camera_web_rtc_fixture(hass):
    """Initialize a demo camera platform with WebRTC."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.camera.Camera.frontend_stream_type",
        new_callable=PropertyMock(return_value=StreamType.WEB_RTC),
    ), patch(
        "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
        return_value=WEBRTC_ANSWER,
    ):
        yield
