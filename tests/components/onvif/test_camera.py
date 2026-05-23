"""Tests for ONVIF camera stream URI cache invalidation on reconnection."""

import asyncio
from unittest.mock import MagicMock, patch

from homeassistant.components.onvif.camera import ONVIFCameraEntity
from homeassistant.components.onvif.device import ONVIFDevice
from homeassistant.components.onvif.event_manager import EventManager
from homeassistant.components.onvif.models import Profile, Resolution, Video
from homeassistant.core import HomeAssistant

from . import HOST, MAC, NAME, PASSWORD, PORT, USERNAME

from tests.common import MockConfigEntry


def _make_camera_entity(
    hass: HomeAssistant,
) -> tuple[ONVIFCameraEntity, ONVIFDevice]:
    """Create a camera entity with a real ONVIFDevice and EventManager."""
    entry = MockConfigEntry(
        domain="onvif",
        data={
            "name": NAME,
            "host": HOST,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD,
        },
        options={},
        entry_id="test_entry",
        unique_id=MAC,
    )
    entry.add_to_hass(hass)

    device = ONVIFDevice(hass, entry)
    device.info = MagicMock()
    device.info.mac = MAC
    device.info.serial_number = None
    device.capabilities = MagicMock()
    device.capabilities.snapshot = False
    device.max_resolution = 1920

    profile = Profile(
        index=0,
        token="token_0",
        name="Profile 0",
        video=Video("H264", Resolution(1920, 1080)),
    )
    device.profiles = [profile]

    mock_onvif_camera = MagicMock()
    event_manager = EventManager(
        hass, mock_onvif_camera, entry, NAME, onvif_device=device
    )
    device.events = event_manager

    camera = ONVIFCameraEntity(device, profile)
    return camera, device


async def test_camera_entity_tracks_unavailable_flag(
    hass: HomeAssistant,
) -> None:
    """Test camera entity sets _was_unavailable when device goes offline."""
    camera, device = _make_camera_entity(hass)

    assert camera._was_unavailable is False

    device.available = False
    with patch.object(camera, "async_write_ha_state"):
        camera._async_event_callback()
    assert camera._was_unavailable is True


async def test_camera_entity_clears_stream_uri_on_reconnect(
    hass: HomeAssistant,
) -> None:
    """Test camera entity clears cached stream URI when device reconnects."""
    camera, device = _make_camera_entity(hass)

    camera._stream_uri = "rtsp://old-uri:554/stream"
    future: asyncio.Future[str] = hass.loop.create_future()
    future.set_result("rtsp://old-uri:554/stream")
    camera._stream_uri_future = future

    # Go offline
    device.available = False
    with patch.object(camera, "async_write_ha_state"):
        camera._async_event_callback()
    assert camera._was_unavailable is True

    # Come back online
    device.available = True
    with patch.object(camera, "async_write_ha_state"):
        camera._async_event_callback()

    assert camera._was_unavailable is False
    assert camera._stream_uri is None
    assert camera._stream_uri_future is None


async def test_camera_entity_no_clear_without_prior_unavailable(
    hass: HomeAssistant,
) -> None:
    """Test camera entity does not clear stream URI without prior unavailable."""
    camera, device = _make_camera_entity(hass)

    camera._stream_uri = "rtsp://current-uri:554/stream"

    assert camera._was_unavailable is False
    assert device.available is True

    # Callback with device available and no prior unavailability
    with patch.object(camera, "async_write_ha_state"):
        camera._async_event_callback()

    assert camera._stream_uri == "rtsp://current-uri:554/stream"
