"""The tests for UVC camera module."""

from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    SUPPORT_STREAM,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.components.uvc import DOMAIN

from tests.common import MockConfigEntry


async def test_camera_v32(hass):
    """Test camera entity for V3.2 servers."""
    with patch(
        "uvcclient.nvr.UVCRemote.index",
        return_value=[{"name": "test camera", "id": "uuid-123"}],
    ), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "3.2.0"}},
    ), patch(
        "uvcclient.nvr.UVCRemote.get_camera", return_value=_get_camera()
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={
                "host": "foo",
                "port": 7447,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
            title="Unifi Video",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    device_registry = await hass.helpers.device_registry.async_get_registry()
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("camera.test_camera")
    assert state is not None
    assert state.name == "test camera"
    assert state.state == "recording"
    assert state.attributes["brand"] == "Ubiquiti"
    assert state.attributes["model_name"] == "UVC"

    entry = entity_registry.async_get("camera.test_camera")
    assert entry.unique_id == "uuid-123"
    assert entry.supported_features == SUPPORT_STREAM

    device = device_registry.async_get(entry.device_id)
    assert device is not None
    assert device.model == "UVC"
    assert device.manufacturer == "Ubiquiti"

    image = await async_get_stream_source(hass, "camera.test_camera")
    assert image == "rtsp://foo:7447/uuid_rtspchannel_0"

    with patch(
        "uvcclient.camera.UVCCameraClientV320.get_snapshot",
        return_value=b"ON",
    ), patch(
        "uvcclient.camera.UVCCameraClientV320.login",
    ):
        image = await async_get_image(hass, "camera.test_camera")
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == b"ON"


async def test_camera_v213(hass):
    """Test camera entity for <V3.2 servers."""
    with patch(
        "uvcclient.nvr.UVCRemote.index",
        return_value=[{"name": "test camera", "uuid": "uuid-123"}],
    ), patch(
        "uvcclient.nvr.UVCRemote._get_bootstrap",
        return_value={"systemInfo": {"version": "2.1.3"}},
    ), patch(
        "uvcclient.nvr.UVCRemote.get_camera",
        return_value=_get_camera(),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            entry_id="uuid",
            unique_id="uuid",
            data={
                "host": "foo",
                "port": 7447,
                "ssl": True,
                "api_key": "test-key",
                "password": "pass",
            },
            title="Unifi Video",
        )
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == config_entries.ENTRY_STATE_LOADED

    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    state = hass.states.get("camera.test_camera")
    assert state is not None

    entry = entity_registry.async_get("camera.test_camera")
    assert entry.unique_id == "uuid-123"
    assert entry.supported_features == SUPPORT_STREAM

    with patch(
        "uvcclient.camera.UVCCameraClient.get_snapshot",
        return_value=b"ON",
    ), patch(
        "uvcclient.camera.UVCCameraClient.login",
    ):
        image = await async_get_image(hass, "camera.test_camera")
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == b"ON"


def _get_camera():
    return {
        "model": "UVC",
        "recordingSettings": {
            "fullTimeRecordEnabled": True,
            "motionRecordEnabled": False,
        },
        "host": "host-a",
        "internalHost": "host-b",
        "username": "admin",
        "lastRecordingStartTime": 1610070992367,
        "channels": [
            {
                "id": "0",
                "width": 1920,
                "height": 1080,
                "fps": 25,
                "bitrate": 6000000,
                "isRtspEnabled": True,
                "rtspUris": [
                    "rtsp://host-a:7447/uuid_rtspchannel_0",
                    "rtsp://foo:7447/uuid_rtspchannel_0",
                ],
            },
            {
                "id": "1",
                "width": 1024,
                "height": 576,
                "fps": 15,
                "bitrate": 1200000,
                "isRtspEnabled": False,
                "rtspUris": [
                    "rtsp://host-a:7447/uuid_rtspchannel_1",
                    "rtsp://foo:7447/uuid_rtspchannel_1",
                ],
            },
        ],
    }
