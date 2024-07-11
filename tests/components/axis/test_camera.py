"""Axis camera platform tests."""

from collections.abc import Callable

import pytest

from homeassistant.components import camera
from homeassistant.components.axis.const import (
    CONF_STREAM_PROFILE,
    DOMAIN as AXIS_DOMAIN,
)
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_IDLE
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import MAC, NAME


async def test_platform_manually_configured(hass: HomeAssistant) -> None:
    """Test that nothing happens when platform is manually configured."""
    assert (
        await async_setup_component(
            hass, CAMERA_DOMAIN, {CAMERA_DOMAIN: {"platform": AXIS_DOMAIN}}
        )
        is True
    )

    assert AXIS_DOMAIN not in hass.data


@pytest.mark.usefixtures("config_entry_setup")
async def test_camera(hass: HomeAssistant) -> None:
    """Test that Axis camera platform is loaded properly."""
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1

    entity_id = f"{CAMERA_DOMAIN}.{NAME}"

    cam = hass.states.get(entity_id)
    assert cam.state == STATE_IDLE
    assert cam.name == NAME

    camera_entity = camera._get_camera_from_entity_id(hass, entity_id)
    assert camera_entity.image_source == "http://1.2.3.4:80/axis-cgi/jpg/image.cgi"
    assert camera_entity.mjpeg_source == "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi"
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264"
    )


@pytest.mark.parametrize("config_entry_options", [{CONF_STREAM_PROFILE: "profile_1"}])
@pytest.mark.usefixtures("config_entry_setup")
async def test_camera_with_stream_profile(hass: HomeAssistant) -> None:
    """Test that Axis camera entity is using the correct path with stream profike."""
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 1

    entity_id = f"{CAMERA_DOMAIN}.{NAME}"

    cam = hass.states.get(entity_id)
    assert cam.state == STATE_IDLE
    assert cam.name == NAME

    camera_entity = camera._get_camera_from_entity_id(hass, entity_id)
    assert camera_entity.image_source == "http://1.2.3.4:80/axis-cgi/jpg/image.cgi"
    assert (
        camera_entity.mjpeg_source
        == "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi?streamprofile=profile_1"
    )
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264&streamprofile=profile_1"
    )


PROPERTY_DATA = f"""root.Properties.API.HTTP.Version=3
root.Properties.API.Metadata.Metadata=yes
root.Properties.API.Metadata.Version=1.0
root.Properties.EmbeddedDevelopment.Version=2.16
root.Properties.Firmware.BuildDate=Feb 15 2019 09:42
root.Properties.Firmware.BuildNumber=26
root.Properties.Firmware.Version=9.10.1
root.Properties.System.SerialNumber={MAC}
"""


@pytest.mark.parametrize("param_properties_payload", [PROPERTY_DATA])
async def test_camera_disabled(
    hass: HomeAssistant, config_entry_factory: Callable[[], ConfigEntry]
) -> None:
    """Test that Axis camera platform is loaded properly but does not create camera entity."""
    await config_entry_factory()
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 0
