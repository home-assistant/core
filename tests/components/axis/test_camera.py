"""Axis camera platform tests."""

from unittest.mock import patch
from urllib.parse import unquote, urlsplit

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import camera
from homeassistant.components.axis.const import CONF_STREAM_PROFILE, CONF_VIDEO_SOURCE
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import ConfigEntryFactoryType
from .const import MAC, NAME


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock camera access token which normally is randomized."""
    with patch(
        "homeassistant.components.camera.entity.SystemRandom.getrandbits",
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
        f"{'' if not stream_profile else f'?{stream_profile}'}"
    )
    assert (
        await camera_entity.stream_source()
        == "rtsp://root:pass@1.2.3.4/axis-media/media.amp?videocodec=h264"
        f"{'' if not stream_profile else f'&{stream_profile}'}"
    )


@pytest.mark.parametrize("param_properties_payload", [PROPERTY_DATA])
@pytest.mark.usefixtures("config_entry_setup")
async def test_camera_disabled(hass: HomeAssistant) -> None:
    """Test Axis camera platform loads but does not create camera entity."""
    assert len(hass.states.async_entity_ids(CAMERA_DOMAIN)) == 0


@pytest.mark.parametrize(
    ("username", "password", "userinfo"),
    [
        pytest.param("root", "pass", "root:pass", id="alphanumeric"),
        pytest.param("root", "pass#word", "root:pass%23word", id="fragment"),
        pytest.param("root", "pass%23word", "root:pass%2523word", id="percent"),
        pytest.param("root", "pass@word", "root:pass%40word", id="at"),
        pytest.param("root", "pass:word", "root:pass%3Aword", id="colon"),
        pytest.param("root", "pass/word", "root:pass%2Fword", id="slash"),
        pytest.param("root", "pass?word", "root:pass%3Fword", id="query"),
        pytest.param("root", "pass word", "root:pass%20word", id="space"),
        pytest.param(
            # aiohttp digest auth rejects ":" in the username
            "user@/?#%",
            "pass@:/?#%",
            "user%40%2F%3F%23%25:pass%40%3A%2F%3F%23%25",
            id="both-components",
        ),
    ],
)
@pytest.mark.parametrize(
    "config_entry_options",
    [{CONF_STREAM_PROFILE: "profile 1", CONF_VIDEO_SOURCE: 2}],
)
async def test_stream_source_credentials(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    config_entry_factory: ConfigEntryFactoryType,
    username: str,
    password: str,
    userinfo: str,
) -> None:
    """Encode each credential without changing the RTSP URL structure."""
    await config_entry_factory()
    hass.config_entries.async_update_entry(
        config_entry,
        data={**config_entry.data, CONF_USERNAME: username, CONF_PASSWORD: password},
    )
    await hass.async_block_till_done()
    camera_entity = camera.helper.get_camera_from_entity_id(
        hass, f"{CAMERA_DOMAIN}.{NAME}"
    )
    source = await camera_entity.stream_source()
    assert source == (
        f"rtsp://{userinfo}@1.2.3.4/axis-media/media.amp"
        "?videocodec=h264&streamprofile=profile+1&camera=2"
    )
    parsed = urlsplit(source)
    assert parsed.hostname == "1.2.3.4"
    assert parsed.path == "/axis-media/media.amp"
    assert parsed.fragment == ""
    assert unquote(parsed.username) == username
    assert unquote(parsed.password) == password
    assert config_entry.data[CONF_USERNAME] == username
    assert config_entry.data[CONF_PASSWORD] == password
