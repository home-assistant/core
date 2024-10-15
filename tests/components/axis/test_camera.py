"""Axis camera platform tests."""

from unittest.mock import patch

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components import camera
from homeassistant.components.axis.const import CONF_STREAM_PROFILE
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType
from .const import MAC, NAME

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock camera access token which normally is randomized."""
    with patch(
        "homeassistant.components.camera.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


PROPERTY_DATA = f"""root.Properties.API.HTTP.Version=3
root.Properties.API.Metadata.Metadata=yes
root.Properties.API.Metadata.Version=1.0
root.Properties.EmbeddedDevelopment.Version=2.16
root.Properties.Firmware.BuildDate=Feb 15 2019 09:42
root.Properties.Firmware.BuildNumber=26
root.Properties.Firmware.Version=9.10.1
root.Properties.System.SerialNumber={MAC}
"""  # No image format data to signal camera support


@pytest.mark.parametrize(
    ("config_entry_options", "stream_profile"),
    [
        ({}, ""),
        ({CONF_STREAM_PROFILE: "profile_1"}, "streamprofile=profile_1"),
    ],
)
async def test_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    config_entry_factory: ConfigEntryFactoryType,
    snapshot: SnapshotAssertion,
    stream_profile: str,
) -> None:
    """Test that Axis camera platform is loaded properly."""
    with patch("homeassistant.components.deconz.PLATFORMS", [Platform.CAMERA]):
        config_entry = await config_entry_factory()
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    entity_id = f"{CAMERA_DOMAIN}.{NAME}"
    camera_entity = camera.helper.get_camera_from_entity_id(hass, entity_id)
    assert camera_entity.image_source == "http://1.2.3.4:80/axis-cgi/jpg/image.cgi"
    assert (
        camera_entity.mjpeg_source == "http://1.2.3.4:80/axis-cgi/mjpg/video.cgi"
        f"{"" if not stream_profile else f"?{stream_profile}"}"
    )
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264"
        f"{"" if not stream_profile else f"&{stream_profile}"}"
    )


@pytest.mark.parametrize("param_properties_payload", [PROPERTY_DATA])
@pytest.mark.usefixtures("config_entry_setup")
async def test_camera_disabled(hass: HomeAssistant) -> None:
    """Test that Axis camera platform is loaded properly but does not create camera entity."""
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 0
