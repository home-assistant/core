"""Test the motionEye camera."""
import copy
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiohttp import web
from aiohttp.web_exceptions import HTTPBadGateway
from motioneye_client.client import (
    MotionEyeClientError,
    MotionEyeClientInvalidAuthError,
)
from motioneye_client.const import (
    KEY_CAMERAS,
    KEY_MOTION_DETECTION,
    KEY_NAME,
    KEY_VIDEO_STREAMING,
)
import pytest

from homeassistant.components.camera import async_get_image, async_get_mjpeg_stream
from homeassistant.components.motioneye import get_motioneye_device_identifier
from homeassistant.components.motioneye.const import (
    CONF_SURVEILLANCE_USERNAME,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MOTIONEYE_MANUFACTURER,
)
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import async_get_registry
import homeassistant.util.dt as dt_util

from . import (
    TEST_CAMERA_DEVICE_IDENTIFIER,
    TEST_CAMERA_ENTITY_ID,
    TEST_CAMERA_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    TEST_CONFIG_ENTRY_ID,
    TEST_SURVEILLANCE_USERNAME,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_setup_camera(hass: HomeAssistant) -> None:
    """Test a basic camera."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"
    assert entity_state.attributes.get("friendly_name") == TEST_CAMERA_NAME


async def test_setup_camera_auth_fail(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientInvalidAuthError)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_client_error(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientError)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_empty_data(hass: HomeAssistant) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_get_cameras = AsyncMock(return_value={})
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_bad_data(hass: HomeAssistant) -> None:
    """Test bad camera data."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    del cameras[KEY_CAMERAS][0][KEY_NAME]

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_without_streaming(hass: HomeAssistant) -> None:
    """Test a camera without streaming enabled."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_VIDEO_STREAMING] = False

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_setup_camera_new_data_same(hass: HomeAssistant) -> None:
    """Test a data refresh with the same data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)  # type: ignore[no-untyped-call]
    await hass.async_block_till_done()
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_new_data_camera_removed(hass: HomeAssistant) -> None:
    """Test a data refresh with a removed camera."""
    device_registry = await async_get_registry(hass)
    entity_registry = await er.async_get_registry(hass)

    client = create_mock_motioneye_client()
    config_entry = await setup_mock_motioneye_config_entry(hass, client=client)

    # Create some random old devices/entity_ids and ensure they get cleaned up.
    old_device_id = "old-device-id"
    old_entity_unique_id = "old-entity-unique_id"
    old_device = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id, identifiers={(DOMAIN, old_device_id)}
    )
    entity_registry.async_get_or_create(
        domain=DOMAIN,
        platform="camera",
        unique_id=old_entity_unique_id,
        config_entry=config_entry,
        device_id=old_device.id,
    )

    await hass.async_block_till_done()
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert device_registry.async_get_device({TEST_CAMERA_DEVICE_IDENTIFIER})  # type: ignore[arg-type]

    client.async_get_cameras = AsyncMock(return_value={KEY_CAMERAS: []})
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)  # type: ignore[no-untyped-call]
    await hass.async_block_till_done()
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert not device_registry.async_get_device({TEST_CAMERA_DEVICE_IDENTIFIER})  # type: ignore[arg-type]
    assert not device_registry.async_get_device({(DOMAIN, old_device_id)})
    assert not entity_registry.async_get_entity_id(
        DOMAIN, "camera", old_entity_unique_id
    )


async def test_setup_camera_new_data_error(hass: HomeAssistant) -> None:
    """Test a data refresh that fails."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    client.async_get_cameras = AsyncMock(side_effect=MotionEyeClientError)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)  # type: ignore[no-untyped-call]
    await hass.async_block_till_done()
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_setup_camera_new_data_without_streaming(hass: HomeAssistant) -> None:
    """Test a data refresh without streaming."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"

    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_VIDEO_STREAMING] = False
    client.async_get_cameras = AsyncMock(return_value=cameras)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)  # type: ignore[no-untyped-call]
    await hass.async_block_till_done()
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "unavailable"


async def test_unload_camera(hass: HomeAssistant) -> None:
    """Test unloading camera."""
    client = create_mock_motioneye_client()
    entry = await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert not client.async_client_close.called
    await hass.config_entries.async_unload(entry.entry_id)
    assert client.async_client_close.called


async def test_get_still_image_from_camera(
    aiohttp_server: Any, hass: HomeAssistant
) -> None:
    """Test getting a still image."""

    image_handler = Mock(return_value="")

    app = web.Application()
    app.add_routes(
        [
            web.get(
                "/foo",
                image_handler,
            )
        ]
    )

    server = await aiohttp_server(app)
    client = create_mock_motioneye_client()
    client.get_camera_snapshot_url = Mock(
        return_value=f"http://localhost:{server.port}/foo"
    )
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_URL: f"http://localhost:{server.port}",
            CONF_SURVEILLANCE_USERNAME: TEST_SURVEILLANCE_USERNAME,
        },
    )

    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()

    # It won't actually get a stream from the dummy handler, so just catch
    # the expected exception, then verify the right handler was called.
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=None)  # type: ignore[no-untyped-call]
    assert image_handler.called


async def test_get_stream_from_camera(aiohttp_server: Any, hass: HomeAssistant) -> None:
    """Test getting a stream."""

    stream_handler = Mock(return_value="")
    app = web.Application()
    app.add_routes([web.get("/", stream_handler)])
    stream_server = await aiohttp_server(app)

    client = create_mock_motioneye_client()
    client.get_camera_stream_url = Mock(
        return_value=f"http://localhost:{stream_server.port}/"
    )
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_URL: f"http://localhost:{stream_server.port}",
            # The port won't be used as the client is a mock.
            CONF_SURVEILLANCE_USERNAME: TEST_SURVEILLANCE_USERNAME,
        },
    )
    cameras = copy.deepcopy(TEST_CAMERAS)
    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(
        hass, config_entry=config_entry, client=client
    )
    await hass.async_block_till_done()

    # It won't actually get a stream from the dummy handler, so just catch
    # the expected exception, then verify the right handler was called.
    with pytest.raises(HTTPBadGateway):
        await async_get_mjpeg_stream(hass, None, TEST_CAMERA_ENTITY_ID)  # type: ignore[no-untyped-call]
    assert stream_handler.called


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test state attributes are set correctly."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.attributes.get("brand") == MOTIONEYE_MANUFACTURER
    assert entity_state.attributes.get("motion_detection")

    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_MOTION_DETECTION] = False
    client.async_get_cameras = AsyncMock(return_value=cameras)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)  # type: ignore[no-untyped-call]
    await hass.async_block_till_done()

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert not entity_state.attributes.get("motion_detection")


async def test_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    client = create_mock_motioneye_client()
    entry = await setup_mock_motioneye_config_entry(hass, client=client)

    device_identifier = get_motioneye_device_identifier(entry.entry_id, TEST_CAMERA_ID)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device({device_identifier})  # type: ignore[arg-type]
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {device_identifier}  # type: ignore[comparison-overlap]
    assert device.manufacturer == MOTIONEYE_MANUFACTURER
    assert device.model == MOTIONEYE_MANUFACTURER
    assert device.name == TEST_CAMERA_NAME

    entity_registry = await er.async_get_registry(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_CAMERA_ENTITY_ID in entities_from_device
