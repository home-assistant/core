"""The tests for the Ring switch platform."""

from unittest.mock import AsyncMock, Mock, patch

from aiohttp.test_utils import make_mocked_request
from freezegun.api import FrozenDateTimeFactory
import pytest
import ring_doorbell
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import camera
from homeassistant.components.ring.camera import FORCE_REFRESH_INTERVAL
from homeassistant.components.ring.const import SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.util.aiohttp import MockStreamReader

from .common import MockConfigEntry, setup_platform

from tests.common import async_fire_time_changed, snapshot_platform

SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)


async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    # Patch getrandbits so the access_token doesn't change on camera attributes
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        await setup_platform(hass, Platform.CAMERA)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("entity_name", "expected_state", "friendly_name"),
    [
        ("camera.internal", True, "Internal"),
        ("camera.front", None, "Front"),
    ],
    ids=["On", "Off"],
)
async def test_camera_motion_detection_state_reports_correctly(
    hass: HomeAssistant,
    mock_ring_client,
    entity_name,
    expected_state,
    friendly_name,
) -> None:
    """Tests that the initial state of a device that should be off is correct."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get(entity_name)
    assert state.attributes.get("motion_detection") is expected_state
    assert state.attributes.get("friendly_name") == friendly_name


async def test_camera_motion_detection_can_be_turned_on_and_off(
    hass: HomeAssistant, mock_ring_client
) -> None:
    """Tests the siren turns on correctly."""
    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is not True

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {"entity_id": "camera.front"},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is True

    await hass.services.async_call(
        "camera",
        "disable_motion_detection",
        {"entity_id": "camera.front"},
        blocking=True,
    )

    await hass.async_block_till_done()

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is None


async def test_camera_motion_detection_not_supported(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Tests the siren turns on correctly."""
    front_camera_mock = mock_ring_devices.get_device(765432)
    has_capability = front_camera_mock.has_capability.side_effect

    def _has_capability(capability):
        if capability == "motion_detection":
            return False
        return has_capability(capability)

    front_camera_mock.has_capability.side_effect = _has_capability

    await setup_platform(hass, Platform.CAMERA)

    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is None

    await hass.services.async_call(
        "camera",
        "enable_motion_detection",
        {"entity_id": "camera.front"},
        blocking=True,
    )

    await hass.async_block_till_done()
    state = hass.states.get("camera.front")
    assert state.attributes.get("motion_detection") is None
    assert (
        "Entity camera.front does not have motion detection capability" in caplog.text
    )


@pytest.mark.parametrize(
    ("exception_type", "reauth_expected"),
    [
        (ring_doorbell.AuthenticationError, True),
        (ring_doorbell.RingTimeout, False),
        (ring_doorbell.RingError, False),
    ],
    ids=["Authentication", "Timeout", "Other"],
)
async def test_motion_detection_errors_when_turned_on(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    exception_type,
    reauth_expected,
) -> None:
    """Tests the motion detection errors are handled correctly."""
    await setup_platform(hass, Platform.CAMERA)
    config_entry = hass.config_entries.async_entries("ring")[0]

    assert not any(config_entry.async_get_active_flows(hass, {SOURCE_REAUTH}))

    front_camera_mock = mock_ring_devices.get_device(765432)
    front_camera_mock.async_set_motion_detection.side_effect = exception_type

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "camera",
            "enable_motion_detection",
            {"entity_id": "camera.front"},
            blocking=True,
        )
    await hass.async_block_till_done()
    front_camera_mock.async_set_motion_detection.assert_called_once()
    assert (
        any(
            flow
            for flow in config_entry.async_get_active_flows(hass, {SOURCE_REAUTH})
            if flow["handler"] == "ring"
        )
        == reauth_expected
    )


async def test_camera_handle_mjpeg_stream(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera returns handle mjpeg stream when available."""
    await setup_platform(hass, Platform.CAMERA)

    front_camera_mock = mock_ring_devices.get_device(765432)
    front_camera_mock.async_recording_url.return_value = None

    state = hass.states.get("camera.front")
    assert state is not None

    mock_request = make_mocked_request("GET", "/", headers={"token": "x"})

    # history not updated yet
    front_camera_mock.async_history.assert_not_called()
    front_camera_mock.async_recording_url.assert_not_called()
    stream = await camera.async_get_mjpeg_stream(hass, mock_request, "camera.front")
    assert stream is None

    # Video url will be none so no  stream
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_history.assert_called_once()
    front_camera_mock.async_recording_url.assert_called_once()

    stream = await camera.async_get_mjpeg_stream(hass, mock_request, "camera.front")
    assert stream is None

    # Stop the history updating so we can update the values manually
    front_camera_mock.async_history = AsyncMock()
    front_camera_mock.last_history[0]["recording"]["status"] = "not ready"
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_called_once()
    stream = await camera.async_get_mjpeg_stream(hass, mock_request, "camera.front")
    assert stream is None

    # If the history id hasn't changed the camera will not check again for the video url
    # until the FORCE_REFRESH_INTERVAL has passed
    front_camera_mock.last_history[0]["recording"]["status"] = "ready"
    front_camera_mock.async_recording_url = AsyncMock(return_value="http://dummy.url")
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_not_called()

    stream = await camera.async_get_mjpeg_stream(hass, mock_request, "camera.front")
    assert stream is None

    freezer.tick(FORCE_REFRESH_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    front_camera_mock.async_recording_url.assert_called_once()

    # Now the stream should be returned
    stream_reader = MockStreamReader(SMALLEST_VALID_JPEG_BYTES)
    with patch("homeassistant.components.ring.camera.CameraMjpeg") as mock_camera:
        mock_camera.return_value.get_reader = AsyncMock(return_value=stream_reader)
        mock_camera.return_value.open_camera = AsyncMock()
        mock_camera.return_value.close = AsyncMock()

        stream = await camera.async_get_mjpeg_stream(hass, mock_request, "camera.front")
        assert stream is not None
        # Check the stream has been read
        assert not await stream_reader.read(-1)


async def test_camera_image(
    hass: HomeAssistant,
    mock_ring_client,
    mock_ring_devices,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test camera will return still image when available."""
    await setup_platform(hass, Platform.CAMERA)

    front_camera_mock = mock_ring_devices.get_device(765432)

    state = hass.states.get("camera.front")
    assert state is not None

    # history not updated yet
    front_camera_mock.async_history.assert_not_called()
    front_camera_mock.async_recording_url.assert_not_called()
    with (
        patch(
            "homeassistant.components.ring.camera.ffmpeg.async_get_image",
            return_value=SMALLEST_VALID_JPEG_BYTES,
        ),
        pytest.raises(HomeAssistantError),
    ):
        image = await camera.async_get_image(hass, "camera.front")

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    # history updated so image available
    front_camera_mock.async_history.assert_called_once()
    front_camera_mock.async_recording_url.assert_called_once()

    with patch(
        "homeassistant.components.ring.camera.ffmpeg.async_get_image",
        return_value=SMALLEST_VALID_JPEG_BYTES,
    ):
        image = await camera.async_get_image(hass, "camera.front")
        assert image.content == SMALLEST_VALID_JPEG_BYTES
