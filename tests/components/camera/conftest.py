"""Test helpers for camera."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import pytest

from homeassistant.components import camera
from homeassistant.components.camera.const import StreamType
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.setup import async_setup_component

from .common import STREAM_SOURCE, WEBRTC_ANSWER


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture(autouse=True)
def camera_only() -> Generator[None]:
    """Enable only the camera platform."""
    with patch(
        "homeassistant.components.demo.COMPONENTS_WITH_CONFIG_ENTRY_DEMO_PLATFORM",
        [Platform.CAMERA],
    ):
        yield


@pytest.fixture(name="mock_camera")
async def mock_camera_fixture(hass: HomeAssistant) -> AsyncGenerator[None]:
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
def mock_camera_hls_fixture(mock_camera: None) -> Generator[None]:
    """Initialize a demo camera platform with HLS."""
    with patch(
        "homeassistant.components.camera.Camera.frontend_stream_type",
        new_callable=PropertyMock(return_value=StreamType.HLS),
    ):
        yield


@pytest.fixture(name="mock_camera_web_rtc")
async def mock_camera_web_rtc_fixture(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Initialize a demo camera platform with WebRTC."""
    assert await async_setup_component(
        hass, "camera", {camera.DOMAIN: {"platform": "demo"}}
    )
    await hass.async_block_till_done()

    with (
        patch(
            "homeassistant.components.camera.Camera.frontend_stream_type",
            new_callable=PropertyMock(return_value=StreamType.WEB_RTC),
        ),
        patch(
            "homeassistant.components.camera.Camera.async_handle_web_rtc_offer",
            return_value=WEBRTC_ANSWER,
        ),
    ):
        yield


@pytest.fixture(name="mock_camera_with_device")
def mock_camera_with_device_fixture() -> Generator[None]:
    """Initialize a demo camera platform with a device."""
    dev_info = DeviceInfo(
        identifiers={("camera", "test_unique_id")},
        name="Test Camera Device",
    )

    class UniqueIdMock(PropertyMock):
        def __get__(self, obj, obj_type=None):
            return obj.name

    with (
        patch(
            "homeassistant.components.camera.Camera.has_entity_name",
            new_callable=PropertyMock(return_value=True),
        ),
        patch("homeassistant.components.camera.Camera.unique_id", new=UniqueIdMock()),
        patch(
            "homeassistant.components.camera.Camera.device_info",
            new_callable=PropertyMock(return_value=dev_info),
        ),
    ):
        yield


@pytest.fixture(name="mock_camera_with_no_name")
def mock_camera_with_no_name_fixture(mock_camera_with_device: None) -> Generator[None]:
    """Initialize a demo camera platform with a device and no name."""
    with patch(
        "homeassistant.components.camera.Camera._attr_name",
        new_callable=PropertyMock(return_value=None),
    ):
        yield


@pytest.fixture(name="mock_stream")
async def mock_stream_fixture(hass: HomeAssistant) -> None:
    """Initialize a demo camera platform with streaming."""
    assert await async_setup_component(hass, "stream", {"stream": {}})


@pytest.fixture(name="mock_stream_source")
def mock_stream_source_fixture() -> Generator[AsyncMock]:
    """Fixture to create an RTSP stream source."""
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        return_value=STREAM_SOURCE,
    ) as mock_stream_source:
        yield mock_stream_source
