"""Axis camera platform tests."""

from homeassistant.components import camera
from homeassistant.components.axis.const import (
    CONF_CAMERA,
    CONF_STREAM_PROFILE,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.setup import async_setup_component

from .test_device import ENTRY_OPTIONS, NAME, setup_axis_integration

from tests.async_mock import patch


async def test_platform_manually_configured(hass):
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass, CAMERA_DOMAIN, {"camera": {"platform": AXIS_DOMAIN}}
        )
        is True
    )

    assert AXIS_DOMAIN not in hass.data


async def test_camera(hass):
    """Test that Axis camera platform is loaded properly."""
    await setup_axis_integration(hass)

    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1

    cam = hass.states.get(f"camera.{NAME}")
    assert cam.state == "idle"
    assert cam.name == NAME

    camera_entity = camera._get_camera_from_entity_id(hass, f"camera.{NAME}")
    assert camera_entity.image_source == "http://1.2.3.4:80/axis-cgi/jpg/image.cgi"
    assert camera_entity.mjpeg_source == "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi"
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264"
    )


async def test_camera_with_stream_profile(hass):
    """Test that Axis camera entity is using the correct path with stream profike."""
    with patch.dict(ENTRY_OPTIONS, {CONF_STREAM_PROFILE: "profile_1"}):
        await setup_axis_integration(hass)

    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1

    cam = hass.states.get(f"camera.{NAME}")
    assert cam.state == "idle"
    assert cam.name == NAME

    camera_entity = camera._get_camera_from_entity_id(hass, f"camera.{NAME}")
    assert camera_entity.image_source == "http://1.2.3.4:80/axis-cgi/jpg/image.cgi"
    assert (
        camera_entity.mjpeg_source
        == "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi?&streamprofile=profile_1"
    )
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264&streamprofile=profile_1"
    )


async def test_camera_disabled(hass):
    """Test that Axis camera platform is loaded properly but does not create camera entity."""
    with patch.dict(ENTRY_OPTIONS, {CONF_CAMERA: False}):
        await setup_axis_integration(hass)

    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 0
