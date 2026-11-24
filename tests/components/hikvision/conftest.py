"""Common fixtures for the Hikvision tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

from pyhik.image import ImageWriteResult, parse_image_capabilities, parse_image_values
from pyhik.isapi import ISAPINotSupportedError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_fixture

from homeassistant.components.hikvision import PLATFORMS
from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant

TEST_HOST = "192.168.1.100"
TEST_PORT = 80
TEST_USERNAME = "admin"
TEST_PASSWORD = "password123"
TEST_DEVICE_ID = "DS-2CD2142FWD-I20170101AAAA"
TEST_DEVICE_NAME = "Front Camera"


@pytest.fixture
def platforms() -> list[Platform]:
    """Platforms, which should be loaded during the test."""
    return PLATFORMS


@pytest.fixture(autouse=True)
async def mock_patch_platforms(platforms: list[Platform]) -> AsyncGenerator[None]:
    """Fixture to set up platforms for tests."""
    with patch(f"homeassistant.components.{DOMAIN}.PLATFORMS", platforms):
        yield


@pytest.fixture(autouse=True)
def mock_isapi_client() -> Generator[MagicMock]:
    """Return a mocked ISAPIClient that offers no image settings by default."""
    with patch("homeassistant.components.hikvision.ISAPIClient") as isapi_mock:
        client = isapi_mock.return_value
        client.get_image_settings.side_effect = ISAPINotSupportedError("not supported")
        client.get_image_channels.side_effect = ISAPINotSupportedError("not supported")
        # Nor detections: see the detections fixture.
        client.get_detection_enabled.side_effect = ISAPINotSupportedError(
            "not supported"
        )
        yield isapi_mock


@pytest.fixture
async def image_values(hass: HomeAssistant) -> dict[str, str]:
    """Return the current image setting values of the test camera."""
    return parse_image_values(
        await async_load_fixture(hass, "image_values.xml", DOMAIN)
    )


@pytest.fixture
async def mock_image_settings(
    hass: HomeAssistant,
    mock_isapi_client: MagicMock,
    image_values: dict[str, str],
) -> MagicMock:
    """Make the mocked camera offer the image settings of a real camera."""
    capabilities = await async_load_fixture(hass, "image_capabilities.xml", DOMAIN)
    values = await async_load_fixture(hass, "image_values.xml", DOMAIN)
    client = mock_isapi_client.return_value
    client.get_image_settings.side_effect = None
    client.get_image_settings.return_value = parse_image_capabilities(
        capabilities, values
    )
    client.get_image_values.return_value = image_values
    client.set_image_setting.return_value = ImageWriteResult(True, 200, "ok")
    client.set_image_linked_setting.return_value = ImageWriteResult(True, 200, "ok")
    return client


@pytest.fixture
def detections() -> dict[str, bool]:
    """Return the detections of the test camera, on or off, as read from a camera.

    Region entrance and exiting, and video loss, it does not have.
    """
    return {
        "motionDetection": True,
        "lineDetection": True,
        "fieldDetection": True,
        "tamperDetection": False,
        "sceneChangeDetection": False,
    }


@pytest.fixture
def mock_detections(
    mock_image_settings: MagicMock, detections: dict[str, bool]
) -> dict[str, bool]:
    """Make the mocked camera have the detections, and keep what is written."""

    def _get(detection: str, channel: int | str = 1) -> bool:
        if detection not in detections:
            raise ISAPINotSupportedError("not supported", 403, "notSupport")
        return detections[detection]

    def _set(detection: str, enabled: bool, channel: int | str = 1) -> ImageWriteResult:
        detections[detection] = enabled
        return ImageWriteResult(True, 200, "ok")

    mock_image_settings.get_detection_enabled.side_effect = _get
    mock_image_settings.set_detection_enabled.side_effect = _set
    return detections


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.hikvision.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title=TEST_DEVICE_NAME,
        domain=DOMAIN,
        version=1,
        minor_version=1,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
        unique_id=TEST_DEVICE_ID,
    )


@pytest.fixture
def amount_of_channels() -> int:
    """Return the default amount of video channels."""
    return 0


@pytest.fixture
def mock_channels(amount_of_channels: int) -> list[MagicMock]:
    """Return a list of mocked VideoChannel objects."""
    channels = []
    for channel_id in range(1, amount_of_channels + 1):
        channel = MagicMock()
        channel.id = channel_id
        channel.name = f"Channel {channel_id}"
        channel.enabled = True
        channels.append(channel)
    return channels


@pytest.fixture
def mock_hik_get_channels(mock_channels: list[MagicMock]) -> Generator[MagicMock]:
    """Return a mocked HikCamera."""
    with patch(
        "homeassistant.components.hikvision.get_video_channels",
    ) as hik_channels_mock:
        hik_channels_mock.return_value = mock_channels
        yield hik_channels_mock


@pytest.fixture
def mock_hikcamera(mock_hik_get_channels: MagicMock) -> Generator[MagicMock]:
    """Return a mocked HikCamera."""
    with (
        patch(
            "homeassistant.components.hikvision.HikCamera",
        ) as hikcamera_mock,
        patch(
            "homeassistant.components.hikvision.config_flow.HikCamera",
            new=hikcamera_mock,
        ),
    ):
        camera = hikcamera_mock.return_value
        camera.get_id = TEST_DEVICE_ID
        camera.get_name = TEST_DEVICE_NAME
        camera.get_type = "Camera"
        camera.auth_failed = False
        camera.stream_auth_failed = False
        camera.current_event_states = {
            "Motion": [(True, 1)],
            "Line Crossing": [(False, 1)],
        }
        camera.fetch_attributes.return_value = (
            False,
            None,
            None,
            "2024-01-01T00:00:00Z",
            None,
        )
        camera.get_event_triggers.return_value = {}
        camera.stream_connected = True

        # pyHik 0.4.0 methods
        camera.get_channels.return_value = [1]
        camera.get_snapshot.return_value = b"fake_image_data"
        camera.get_stream_url.return_value = (
            f"rtsp://{TEST_USERNAME}:{TEST_PASSWORD}"
            f"@{TEST_HOST}:554/Streaming/Channels/1"
        )

        yield hikcamera_mock


@pytest.fixture
def mock_hik_nvr(mock_hikcamera: MagicMock) -> MagicMock:
    """Return a mocked HikCamera configured as an NVR."""
    camera = mock_hikcamera.return_value
    camera.get_type = "NVR"
    camera.current_event_states = {}
    camera.get_event_triggers.return_value = {"VMD": [1, 2]}
    return mock_hikcamera
