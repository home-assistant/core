"""The tests for UVC camera module."""

from datetime import UTC, datetime, timedelta
from unittest.mock import call, patch

import pytest
from uvcclient import camera, nvr

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    SERVICE_DISABLE_MOTION,
    SERVICE_ENABLE_MOTION,
    CameraEntityFeature,
    CameraState,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed


@pytest.fixture(name="mock_remote")
def mock_remote_fixture(camera_info):
    """Mock the nvr.UVCRemote class."""
    with patch("homeassistant.components.uvc.camera.nvr.UVCRemote") as mock_remote:

        def setup(host, port, apikey, ssl=False):
            """Set instance attributes."""
            mock_remote.return_value._host = host
            mock_remote.return_value._port = port
            mock_remote.return_value._apikey = apikey
            mock_remote.return_value._ssl = ssl
            return mock_remote.return_value

        mock_remote.side_effect = setup
        mock_remote.return_value.get_camera.return_value = camera_info
        mock_cameras = [
            {"uuid": "one", "name": "Front", "id": "id1"},
            {"uuid": "two", "name": "Back", "id": "id2"},
        ]
        mock_remote.return_value.index.return_value = mock_cameras
        mock_remote.return_value.server_version = (3, 2, 0)
        mock_remote.return_value.camera_identifier = "id"
        yield mock_remote


@pytest.fixture(name="camera_info")
def camera_info_fixture():
    """Mock the camera info of a camera."""
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


@pytest.fixture(name="camera_v320")
def camera_v320_fixture():
    """Mock the v320 camera."""
    with patch(
        "homeassistant.components.uvc.camera.uvc_camera.UVCCameraClientV320"
    ) as camera:
        camera.return_value.get_snapshot.return_value = "test_image"
        yield camera


@pytest.fixture(name="camera_v313")
def camera_v313_fixture():
    """Mock the v320 camera."""
    with patch(
        "homeassistant.components.uvc.camera.uvc_camera.UVCCameraClient"
    ) as camera:
        camera.return_value.get_snapshot.return_value = "test_image"
        yield camera


async def test_setup_full_config(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_remote, camera_info
) -> None:
    """Test the setup with full configuration."""
    config = {
        "platform": "uvc",
        "nvr": "foo",
        "password": "bar",
        "port": 123,
        "key": "secret",
    }

    def mock_get_camera(uuid):
        """Create a mock camera."""
        if uuid == "id3":
            camera_info["model"] = "airCam"

        return camera_info

    mock_remote.return_value.index.return_value.append(
        {"uuid": "three", "name": "Old AirCam", "id": "id3"}
    )
    mock_remote.return_value.get_camera.side_effect = mock_get_camera

    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    assert mock_remote.call_count == 1
    assert mock_remote.call_args == call("foo", 123, "secret", ssl=False)

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == 2

    state = hass.states.get("camera.front")

    assert state
    assert state.name == "Front"

    state = hass.states.get("camera.back")

    assert state
    assert state.name == "Back"

    entity_entry = entity_registry.async_get("camera.front")

    assert entity_entry.unique_id == "id1"

    entity_entry = entity_registry.async_get("camera.back")

    assert entity_entry.unique_id == "id2"


async def test_setup_partial_config(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_remote
) -> None:
    """Test the setup with partial configuration."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}

    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    assert mock_remote.call_count == 1
    assert mock_remote.call_args == call("foo", 7080, "secret", ssl=False)

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == 2

    state = hass.states.get("camera.front")

    assert state
    assert state.name == "Front"

    state = hass.states.get("camera.back")

    assert state
    assert state.name == "Back"

    entity_entry = entity_registry.async_get("camera.front")

    assert entity_entry.unique_id == "id1"

    entity_entry = entity_registry.async_get("camera.back")

    assert entity_entry.unique_id == "id2"


async def test_setup_partial_config_v31x(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, mock_remote
) -> None:
    """Test the setup with a v3.1.x server."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    mock_remote.return_value.server_version = (3, 1, 3)
    mock_remote.return_value.camera_identifier = "uuid"

    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    assert mock_remote.call_count == 1
    assert mock_remote.call_args == call("foo", 7080, "secret", ssl=False)

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == 2

    state = hass.states.get("camera.front")

    assert state
    assert state.name == "Front"

    state = hass.states.get("camera.back")

    assert state
    assert state.name == "Back"

    entity_entry = entity_registry.async_get("camera.front")

    assert entity_entry.unique_id == "one"

    entity_entry = entity_registry.async_get("camera.back")

    assert entity_entry.unique_id == "two"


@pytest.mark.parametrize(
    "config",
    [
        {"platform": "uvc", "nvr": "foo"},
        {"platform": "uvc", "key": "secret"},
        {"platform": "uvc", "nvr": "foo", "key": "secret", "port": "invalid"},
    ],
)
async def test_setup_incomplete_config(
    hass: HomeAssistant, mock_remote, config
) -> None:
    """Test the setup with incomplete or invalid configuration."""
    assert await async_setup_component(hass, "camera", config)
    await hass.async_block_till_done()

    camera_states = hass.states.async_all("camera")

    assert not camera_states


@pytest.mark.parametrize(
    ("error", "ready_states"),
    [
        (nvr.NotAuthorized, 0),
        (nvr.NvrError, 2),
    ],
)
async def test_setup_nvr_errors_during_indexing(
    hass: HomeAssistant, mock_remote, error, ready_states
) -> None:
    """Set up test for NVR errors during indexing."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    now = utcnow()
    mock_remote.return_value.index.side_effect = error
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    camera_states = hass.states.async_all("camera")

    assert not camera_states

    # resolve the error
    mock_remote.return_value.index.side_effect = None

    async_fire_time_changed(hass, now + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == ready_states


@pytest.mark.parametrize(
    ("error", "ready_states"),
    [
        (nvr.NotAuthorized, 0),
        (nvr.NvrError, 2),
    ],
)
async def test_setup_nvr_errors_during_initialization(
    hass: HomeAssistant, mock_remote, error, ready_states
) -> None:
    """Set up test for NVR errors during initialization."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    now = utcnow()
    mock_remote.side_effect = error
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    assert not mock_remote.index.called

    camera_states = hass.states.async_all("camera")

    assert not camera_states

    # resolve the error
    mock_remote.side_effect = None

    async_fire_time_changed(hass, now + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == ready_states


async def test_properties(hass: HomeAssistant, mock_remote) -> None:
    """Test the properties."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    camera_states = hass.states.async_all("camera")

    assert len(camera_states) == 2

    state = hass.states.get("camera.front")

    assert state
    assert state.name == "Front"
    assert state.state == CameraState.RECORDING
    assert state.attributes["brand"] == "Ubiquiti"
    assert state.attributes["model_name"] == "UVC"
    assert state.attributes["supported_features"] == CameraEntityFeature.STREAM


async def test_motion_recording_mode_properties(
    hass: HomeAssistant, mock_remote
) -> None:
    """Test the properties."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    now = utcnow()
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert state.state == CameraState.RECORDING

    mock_remote.return_value.get_camera.return_value["recordingSettings"][
        "fullTimeRecordEnabled"
    ] = False
    mock_remote.return_value.get_camera.return_value["recordingSettings"][
        "motionRecordEnabled"
    ] = True

    async_fire_time_changed(hass, now + timedelta(seconds=31))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.front")

    assert state
    assert state.state != CameraState.RECORDING
    assert state.attributes["last_recording_start_time"] == datetime(
        2021, 1, 8, 1, 56, 32, 367000, tzinfo=UTC
    )

    mock_remote.return_value.get_camera.return_value["recordingIndicator"] = "DISABLED"

    async_fire_time_changed(hass, now + timedelta(seconds=61))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.front")

    assert state
    assert state.state != CameraState.RECORDING

    mock_remote.return_value.get_camera.return_value["recordingIndicator"] = (
        "MOTION_INPROGRESS"
    )

    async_fire_time_changed(hass, now + timedelta(seconds=91))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.front")

    assert state
    assert state.state == CameraState.RECORDING

    mock_remote.return_value.get_camera.return_value["recordingIndicator"] = (
        "MOTION_FINISHED"
    )

    async_fire_time_changed(hass, now + timedelta(seconds=121))
    await hass.async_block_till_done(wait_background_tasks=True)

    state = hass.states.get("camera.front")

    assert state
    assert state.state == CameraState.RECORDING


async def test_stream(hass: HomeAssistant, mock_remote) -> None:
    """Test the RTSP stream URI."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    stream_source = await async_get_stream_source(hass, "camera.front")

    assert stream_source == "rtsp://foo:7447/uuid_rtspchannel_0"


async def test_login(hass: HomeAssistant, mock_remote, camera_v320) -> None:
    """Test the login."""
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    image = await async_get_image(hass, "camera.front")

    assert camera_v320.call_count == 1
    assert camera_v320.call_args == call("host-a", "admin", "ubnt")
    assert camera_v320.return_value.login.call_count == 1
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == "test_image"


async def test_login_v31x(hass: HomeAssistant, mock_remote, camera_v313) -> None:
    """Test login with v3.1.x server."""
    mock_remote.return_value.server_version = (3, 1, 3)
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    image = await async_get_image(hass, "camera.front")

    assert camera_v313.call_count == 1
    assert camera_v313.call_args == call("host-a", "admin", "ubnt")
    assert camera_v313.return_value.login.call_count == 1
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == "test_image"


@pytest.mark.parametrize(
    "error", [OSError, camera.CameraConnectError, camera.CameraAuthError]
)
async def test_login_tries_both_addrs_and_caches(
    hass: HomeAssistant, mock_remote, camera_v320, error
) -> None:
    """Test the login tries."""
    responses = [0]

    def mock_login(*a):
        """Mock login."""
        try:
            responses.pop(0)
            raise error
        except IndexError:
            pass

    snapshots = [0]

    def mock_snapshots(*a):
        """Mock get snapshots."""
        try:
            snapshots.pop(0)
            raise camera.CameraAuthError
        except IndexError:
            pass
        return "test_image"

    camera_v320.return_value.login.side_effect = mock_login

    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    image = await async_get_image(hass, "camera.front")

    assert camera_v320.call_count == 2
    assert camera_v320.call_args == call("host-b", "admin", "ubnt")
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == "test_image"

    camera_v320.reset_mock()
    camera_v320.return_value.get_snapshot.side_effect = mock_snapshots

    image = await async_get_image(hass, "camera.front")

    assert camera_v320.call_count == 1
    assert camera_v320.call_args == call("host-b", "admin", "ubnt")
    assert camera_v320.return_value.login.call_count == 1
    assert image.content_type == DEFAULT_CONTENT_TYPE
    assert image.content == "test_image"


async def test_login_fails_both_properly(
    hass: HomeAssistant, mock_remote, camera_v320
) -> None:
    """Test if login fails properly."""
    camera_v320.return_value.login.side_effect = OSError
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, "camera.front")

    assert camera_v320.return_value.get_snapshot.call_count == 0


@pytest.mark.parametrize(
    ("source_error", "raised_error", "snapshot_calls"),
    [
        (camera.CameraConnectError, HomeAssistantError, 1),
        (camera.CameraAuthError, camera.CameraAuthError, 2),
    ],
)
async def test_camera_image_error(
    hass: HomeAssistant,
    mock_remote,
    camera_v320,
    source_error,
    raised_error,
    snapshot_calls,
) -> None:
    """Test the camera image error."""
    camera_v320.return_value.get_snapshot.side_effect = source_error
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    with pytest.raises(raised_error):
        await async_get_image(hass, "camera.front")

    assert camera_v320.return_value.get_snapshot.call_count == snapshot_calls


async def test_enable_disable_motion_detection(
    hass: HomeAssistant, mock_remote, camera_info
) -> None:
    """Test enable and disable motion detection."""

    def set_recordmode(uuid, mode):
        """Set record mode."""
        motion_record_enabled = mode == "motion"
        camera_info["recordingSettings"]["motionRecordEnabled"] = motion_record_enabled

    mock_remote.return_value.set_recordmode.side_effect = set_recordmode
    config = {"platform": "uvc", "nvr": "foo", "key": "secret"}
    assert await async_setup_component(hass, "camera", {"camera": config})
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert "motion_detection" not in state.attributes

    await hass.services.async_call(
        "camera", SERVICE_ENABLE_MOTION, {"entity_id": "camera.front"}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert state.attributes["motion_detection"]

    await hass.services.async_call(
        "camera", SERVICE_DISABLE_MOTION, {"entity_id": "camera.front"}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert "motion_detection" not in state.attributes

    mock_remote.return_value.set_recordmode.side_effect = nvr.NvrError

    await hass.services.async_call(
        "camera", SERVICE_ENABLE_MOTION, {"entity_id": "camera.front"}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert "motion_detection" not in state.attributes

    mock_remote.return_value.set_recordmode.side_effect = set_recordmode

    await hass.services.async_call(
        "camera", SERVICE_ENABLE_MOTION, {"entity_id": "camera.front"}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert state.attributes["motion_detection"]

    mock_remote.return_value.set_recordmode.side_effect = nvr.NvrError

    await hass.services.async_call(
        "camera", SERVICE_DISABLE_MOTION, {"entity_id": "camera.front"}, True
    )
    await hass.async_block_till_done()

    state = hass.states.get("camera.front")

    assert state
    assert state.attributes["motion_detection"]
