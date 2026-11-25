"""Tests for the Bambu Lab camera platform."""

from collections.abc import Generator
from dataclasses import replace
from unittest.mock import AsyncMock, MagicMock, patch

from aiobambulab import BambuLabConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    CameraEntityFeature,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.const import ATTR_SUPPORTED_FEATURES, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import push_update, setup_integration

CAMERA = "camera.x1_carbon_camera"
STREAM_URL = "rtsps://bblp:12345678@192.168.1.50:322/streaming/live/1"


@pytest.fixture(autouse=True)
def mock_access_token() -> Generator[None]:
    """Mock the access token of a camera, which is random."""
    with patch(
        "homeassistant.components.camera.entity.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


@pytest.fixture
def mock_image_camera(mock_bambu_lab_client: MagicMock) -> MagicMock:
    """Return the client of a printer that sends images of its camera."""
    mock_bambu_lab_client.supports_camera_images = True
    mock_bambu_lab_client.camera_image.return_value = b"image"
    return mock_bambu_lab_client


@pytest.fixture
def mock_stream_camera(mock_bambu_lab_client: MagicMock) -> MagicMock:
    """Return the client of a printer that serves a video stream."""
    mock_bambu_lab_client.state = replace(
        mock_bambu_lab_client.state, camera_stream_enabled=True
    )
    mock_bambu_lab_client.camera_stream_url = STREAM_URL
    return mock_bambu_lab_client


@pytest.mark.parametrize(
    "client_fixture",
    [
        pytest.param("mock_image_camera", id="images"),
        pytest.param("mock_stream_camera", id="stream"),
    ],
)
async def test_cameras(
    hass: HomeAssistant,
    request: pytest.FixtureRequest,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    client_fixture: str,
) -> None:
    """Test the camera of a printer."""
    request.getfixturevalue(client_fixture)

    with patch("homeassistant.components.bambu_lab._PLATFORMS", [Platform.CAMERA]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_bambu_lab_client")
async def test_no_camera(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test a printer without a camera that can be reached has no camera."""
    await setup_integration(hass, mock_config_entry)

    assert hass.states.get(CAMERA) is None


async def test_image(
    hass: HomeAssistant,
    mock_image_camera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the camera shows the image the printer sends."""
    await setup_integration(hass, mock_config_entry)

    image = await async_get_image(hass, CAMERA)

    assert image.content == b"image"
    assert not hass.states.get(CAMERA).attributes[ATTR_SUPPORTED_FEATURES]


async def test_image_error(
    hass: HomeAssistant,
    mock_image_camera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the camera has no image when the printer does not send one."""
    await setup_integration(hass, mock_config_entry)
    mock_image_camera.camera_image.side_effect = BambuLabConnectionError

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, CAMERA)


@pytest.mark.usefixtures("mock_stream_camera")
async def test_stream(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test the camera gives the video stream of the printer."""
    await setup_integration(hass, mock_config_entry)

    assert await async_get_stream_source(hass, CAMERA) == STREAM_URL
    assert (
        hass.states.get(CAMERA).attributes[ATTR_SUPPORTED_FEATURES]
        == CameraEntityFeature.STREAM
    )


async def test_stream_turned_off(
    hass: HomeAssistant,
    mock_stream_camera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the camera is unavailable while the printer does not serve the stream."""
    await setup_integration(hass, mock_config_entry)

    mock_stream_camera.state = replace(
        mock_stream_camera.state, camera_stream_enabled=False
    )
    mock_stream_camera.camera_stream_url = None
    push_update(mock_stream_camera)
    await hass.async_block_till_done()

    assert hass.states.get(CAMERA).state == STATE_UNAVAILABLE

    mock_stream_camera.camera_stream_url = STREAM_URL
    push_update(mock_stream_camera)
    await hass.async_block_till_done()

    assert hass.states.get(CAMERA).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("mock_stream_camera")
async def test_image_from_stream(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the image of a camera with a video stream comes from that stream."""
    await setup_integration(hass, mock_config_entry)

    with patch(
        "homeassistant.components.camera.entity.create_stream"
    ) as mock_create_stream:
        mock_create_stream.return_value.async_get_image = AsyncMock(
            return_value=b"frame"
        )
        image = await async_get_image(hass, CAMERA)

    assert image.content == b"frame"
    assert mock_create_stream.call_args.args[1] == STREAM_URL


@pytest.mark.usefixtures("mock_stream_camera")
async def test_mjpeg_from_stream(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the MJPEG stream of a camera with a video stream has its images."""
    await setup_integration(hass, mock_config_entry)
    client = await hass_client()

    with patch(
        "homeassistant.components.camera.entity.create_stream"
    ) as mock_create_stream:
        mock_create_stream.return_value.async_get_image = AsyncMock(
            return_value=b"frame"
        )
        response = await client.get(f"/api/camera_proxy_stream/{CAMERA}")
        chunk = await response.content.readuntil(b"frame")
        response.close()

    assert chunk.endswith(b"frame")
    assert mock_create_stream.call_args.args[1] == STREAM_URL
