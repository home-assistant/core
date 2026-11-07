"""Test camera media source."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import media_source
from homeassistant.components.camera import CameraCapabilities
from homeassistant.components.camera.const import StreamType
from homeassistant.components.stream import FORMAT_CONTENT_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.setup import async_setup_component

from .conftest import HISTORY_ID, LIVE_ID, PAST, HistoryCamera


@pytest.fixture(autouse=True)
async def setup_media_source(hass: HomeAssistant) -> None:
    """Set up media source."""
    assert await async_setup_component(hass, "media_source", {})


@pytest.mark.usefixtures("mock_camera_with_device", "mock_camera")
async def test_device_with_device(hass: HomeAssistant) -> None:
    """Test browsing when camera has a device and a name."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 2
    assert len(item.children) == 1
    assert item.children[0].title == "Test Camera Device Demo camera without stream"


@pytest.mark.usefixtures("mock_camera_with_no_name", "mock_camera")
async def test_device_with_no_name(hass: HomeAssistant) -> None:
    """Test browsing when camera has device and name == None."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 2
    assert len(item.children) == 1
    assert item.children[0].title == "Test Camera Device Demo camera without stream"


@pytest.mark.usefixtures("mock_camera_hls")
async def test_browsing_hls(hass: HomeAssistant) -> None:
    """Test browsing HLS camera media source."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 0
    assert item.not_shown == 3

    # Adding stream enables HLS camera
    hass.config.components.add("stream")

    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item.not_shown == 0
    assert len(item.children) == 3
    assert item.children[0].media_content_type == FORMAT_CONTENT_TYPE["hls"]


@pytest.mark.usefixtures("mock_camera")
async def test_browsing_mjpeg(hass: HomeAssistant) -> None:
    """Test browsing MJPEG camera media source."""
    item = await media_source.async_browse_media(hass, "media-source://camera")
    assert item is not None
    assert item.title == "Camera"
    assert len(item.children) == 1
    assert item.not_shown == 2
    assert item.children[0].media_content_type == "image/jpg"
    assert item.children[0].title == "Demo camera without stream"


@pytest.mark.usefixtures("mock_camera_webrtc")
async def test_browsing_webrtc(hass: HomeAssistant) -> None:
    """Test browsing WebRTC camera media source."""
    # 3 cameras:
    # one only supports WebRTC (no stream source)
    # one raises when getting the source
    # One has a stream source, and should be the only browsable one
    with patch(
        "homeassistant.components.camera.Camera.stream_source",
        side_effect=["test", None, Exception],
    ):
        item = await media_source.async_browse_media(hass, "media-source://camera")
        assert item is not None
        assert item.title == "Camera"
        assert len(item.children) == 0
        assert item.not_shown == 3

        # Adding stream enables HLS camera
        hass.config.components.add("stream")

        item = await media_source.async_browse_media(hass, "media-source://camera")
        assert item.not_shown == 2
        assert len(item.children) == 1
        assert item.children[0].media_content_type == FORMAT_CONTENT_TYPE["hls"]


@pytest.mark.usefixtures("mock_camera")
async def test_resolving(hass: HomeAssistant) -> None:
    """Test resolving."""
    # Adding stream enables HLS camera
    hass.config.components.add("stream")

    with patch(
        "homeassistant.components.camera.media_source.async_stream_endpoint_url",
        return_value="http://example.com/stream",
    ):
        item = await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert item is not None
    assert item.url == "http://example.com/stream"
    assert item.mime_type == FORMAT_CONTENT_TYPE["hls"]


@pytest.mark.usefixtures("mock_camera")
async def test_resolving_errors(hass: HomeAssistant) -> None:
    """Test resolving."""

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert str(exc_info.value) == "Stream integration not loaded"

    hass.config.components.add("stream")

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.non_existing", None
        )
    assert str(exc_info.value) == "Could not resolve media item: camera.non_existing"

    with (
        pytest.raises(media_source.Unresolvable) as exc_info,
        patch(
            "homeassistant.components.camera.Camera.camera_capabilities",
            new_callable=PropertyMock(
                return_value=CameraCapabilities({StreamType.WEB_RTC})
            ),
        ),
    ):
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert str(exc_info.value) == "Camera does not support MJPEG or HLS streaming."

    with pytest.raises(media_source.Unresolvable) as exc_info:
        await media_source.async_resolve_media(
            hass, "media-source://camera/camera.demo_camera", None
        )
    assert str(exc_info.value) == "Camera camera.demo_camera does not support streaming"


@pytest.mark.usefixtures("mock_camera")
async def test_get_media_image(hass: HomeAssistant) -> None:
    """Test getting a snapshot of a camera."""
    assert await media_source.async_get_media_image(
        hass, "media-source://camera/camera.demo_camera"
    ) == media_source.MediaImage(b"Test", "image/jpg")


@pytest.mark.usefixtures("mock_camera")
async def test_get_media_image_non_existing_camera(hass: HomeAssistant) -> None:
    """Test getting a snapshot of a non existing camera."""
    with pytest.raises(
        media_source.Unresolvable,
        match="Could not resolve media item: camera.non_existing",
    ):
        await media_source.async_get_media_image(
            hass, "media-source://camera/camera.non_existing"
        )


@pytest.mark.usefixtures("mock_camera")
async def test_get_media_image_camera_off(hass: HomeAssistant) -> None:
    """Test getting a snapshot of a camera that is off."""
    with (
        patch(
            "homeassistant.components.camera.Camera.is_on",
            new_callable=PropertyMock(return_value=False),
        ),
        pytest.raises(
            media_source.Unresolvable, match="Camera camera.demo_camera is off"
        ),
    ):
        await media_source.async_get_media_image(
            hass, "media-source://camera/camera.demo_camera"
        )


async def test_get_media_image_past(
    hass: HomeAssistant, history_camera: HistoryCamera
) -> None:
    """A timestamp after the entity id returns the recorded image."""
    image = await media_source.async_get_media_image(
        hass, f"media-source://camera/{HISTORY_ID}/2020-10-20T08:00:00+02:00"
    )

    assert image.content == b"past"
    assert image.mime_type == "image/jpeg"
    assert history_camera.past_calls == [PAST]


@pytest.mark.usefixtures("history_camera")
@pytest.mark.parametrize(
    "suffix", ["", "yesterday", "2026-13-45T00:00:00Z"], ids=["empty", "text", "date"]
)
async def test_get_media_image_past_invalid(hass: HomeAssistant, suffix: str) -> None:
    """A timestamp that does not parse is unresolvable, not the live image."""
    with pytest.raises(media_source.Unresolvable, match="Invalid timestamp"):
        await media_source.async_get_media_image(
            hass, f"media-source://camera/{HISTORY_ID}/{suffix}"
        )


async def test_get_media_image_past_camera_off(
    hass: HomeAssistant, history_camera: HistoryCamera
) -> None:
    """A camera that is off gives no past image."""
    history_camera._attr_is_on = False

    with pytest.raises(HomeAssistantError) as exc_info:
        await media_source.async_get_media_image(
            hass, f"media-source://camera/{HISTORY_ID}/2020-10-20T06:00:00Z"
        )
    assert exc_info.value.translation_key == "camera_off"
    assert history_camera.past_calls == []


@pytest.mark.usefixtures("history_camera")
async def test_get_media_image_past_not_supported(hass: HomeAssistant) -> None:
    """A camera without history raises like the snapshot action."""
    with pytest.raises(ServiceValidationError) as exc_info:
        await media_source.async_get_media_image(
            hass, f"media-source://camera/{LIVE_ID}/2020-10-20T06:00:00Z"
        )
    assert exc_info.value.translation_key == "past_image_not_supported"


@pytest.mark.usefixtures("history_camera")
async def test_resolving_past_image(hass: HomeAssistant) -> None:
    """A past image can't be played."""
    with pytest.raises(media_source.Unresolvable):
        await media_source.async_resolve_media(
            hass, f"media-source://camera/{HISTORY_ID}/2020-10-20T06:00:00Z", None
        )
