"""Tests for Shelly camera platform."""

from collections.abc import Generator
from copy import deepcopy
from unittest.mock import Mock, patch

from aioshelly.const import MODEL_CAMERA
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.camera import (
    DATA_COMPONENT,
    DOMAIN as CAMERA_DOMAIN,
    CameraState,
    get_camera_from_entity_id,
)
from homeassistant.components.shelly.const import CONF_SLEEP_PERIOD
from homeassistant.const import (
    CONF_HOST,
    CONF_MODEL,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import EntityRegistry

from . import MOCK_MAC, init_integration, patch_platforms, register_entity

from tests.common import snapshot_platform

CAMERA_ENTITY_ID = "camera.test_name_stream_0"


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms under test."""
    with patch_platforms([Platform.CAMERA]):
        yield


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_entity_setup(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    entity_registry: EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test camera entity is created with correct unique_id and initial state."""
    with patch("random.SystemRandom.getrandbits", return_value=123123123123):
        entry = await init_integration(hass, 3, model=MODEL_CAMERA)

    assert hass.states.get(CAMERA_ENTITY_ID)
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)

    assert (er_entry := entity_registry.async_get(CAMERA_ENTITY_ID))
    assert er_entry.unique_id == f"{MOCK_MAC}-camera:0-stream_0"


async def test_camera_state_streaming(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test camera state is streaming when streams > 0."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    new_status = deepcopy(mock_camera_rpc_device.status)
    new_status["camera:0"]["streams"] = 1
    monkeypatch.setattr(mock_camera_rpc_device, "status", new_status)
    mock_camera_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(CAMERA_ENTITY_ID))
    assert state.state == CameraState.STREAMING


async def test_camera_state_recording(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test camera state is recording when recordings is set."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    new_status = deepcopy(mock_camera_rpc_device.status)
    new_status["camera:0"]["recordings"] = {"id": 1}
    monkeypatch.setattr(mock_camera_rpc_device, "status", new_status)
    mock_camera_rpc_device.mock_update()
    await hass.async_block_till_done()

    assert (state := hass.states.get(CAMERA_ENTITY_ID))
    assert state.state == CameraState.RECORDING


async def test_camera_use_stream_for_stills(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
) -> None:
    """Test use_stream_for_stills returns True (still images from the RTSP stream)."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    camera = get_camera_from_entity_id(hass, CAMERA_ENTITY_ID)
    assert camera.use_stream_for_stills is True


async def test_camera_stream_source(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
) -> None:
    """Test stream_source returns the RTSP URL for go2rtc."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    camera = get_camera_from_entity_id(hass, CAMERA_ENTITY_ID)
    result = await camera.stream_source()
    assert result == "rtsp://192.168.1.37/stream/0"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_camera_stream_source_stream_1(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
) -> None:
    """Test stream_source returns correct RTSP URL for stream 1."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    camera = get_camera_from_entity_id(hass, "camera.test_name_stream_1")
    result = await camera.stream_source()
    assert result == "rtsp://192.168.1.37/stream/1"


@pytest.mark.parametrize(
    ("password", "expected_password"),
    [
        ("password", "password"),
        ("pass:word@1", "pass%3Aword%401"),
    ],
)
async def test_camera_stream_source_with_credentials(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    password: str,
    expected_password: str,
) -> None:
    """Test stream_source returns the RTSP URL with credentials for go2rtc."""
    await init_integration(
        hass,
        3,
        model=MODEL_CAMERA,
        data={
            CONF_HOST: "192.168.1.37",
            CONF_MODEL: MODEL_CAMERA,
            CONF_PASSWORD: password,
            CONF_SLEEP_PERIOD: 0,
            CONF_USERNAME: "admin",
        },
    )

    camera = get_camera_from_entity_id(hass, CAMERA_ENTITY_ID)
    result = await camera.stream_source()
    assert result == f"rtsp://admin:{expected_password}@192.168.1.37/stream/0"


async def test_camera_off_when_streamer_stopped(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test camera is off when the streamer is not running."""
    status = deepcopy(mock_camera_rpc_device.status)
    status["camera:0"]["streamer"] = "stopped"
    monkeypatch.setattr(mock_camera_rpc_device, "status", status)

    await init_integration(hass, 3, model=MODEL_CAMERA)

    camera = hass.data[DATA_COMPONENT].get_entity(CAMERA_ENTITY_ID)
    assert camera is not None
    assert camera.is_on is False


async def test_camera_properties_when_device_not_initialized(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test camera properties return safe values when the device is not initialized."""
    await init_integration(hass, 3, model=MODEL_CAMERA)

    camera = get_camera_from_entity_id(hass, CAMERA_ENTITY_ID)

    monkeypatch.setattr(mock_camera_rpc_device, "initialized", False)

    assert camera.is_on is False
    assert camera.available is False


async def test_camera_not_created_when_rtsp_disabled(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test camera entities are not created when RTSP is disabled."""
    new_config = deepcopy(mock_camera_rpc_device.config)
    new_config["camera:0"]["rtsp"]["enable"] = False
    monkeypatch.setattr(mock_camera_rpc_device, "config", new_config)

    await init_integration(hass, 3, model=MODEL_CAMERA)

    assert hass.states.get(CAMERA_ENTITY_ID) is None
    assert entity_registry.async_get(CAMERA_ENTITY_ID) is None


async def test_rpc_camera_removal_when_rtsp_disabled(
    hass: HomeAssistant,
    mock_camera_rpc_device: Mock,
    monkeypatch: pytest.MonkeyPatch,
    entity_registry: EntityRegistry,
) -> None:
    """Test RPC camera is removed due to removal_condition when RTSP disabled."""
    entity_id = register_entity(
        hass, CAMERA_DOMAIN, "test_name_stream_0", "camera:0-stream_0"
    )

    assert entity_registry.async_get(entity_id) is not None

    new_config = deepcopy(mock_camera_rpc_device.config)
    new_config["camera:0"]["rtsp"]["enable"] = False
    monkeypatch.setattr(mock_camera_rpc_device, "config", new_config)

    await init_integration(hass, 3, model=MODEL_CAMERA)

    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None
