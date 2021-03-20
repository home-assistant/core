"""Test the motionEye camera."""
import copy
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiohttp import web  # type: ignore
from aiohttp.web_exceptions import HTTPBadGateway
from motioneye_client.client import MotionEyeClientError, MotionEyeClientInvalidAuth
from motioneye_client.const import KEY_CAMERAS, KEY_NAME, KEY_VIDEO_STREAMING
import pytest

from homeassistant.components.camera import async_get_image, async_get_mjpeg_stream
from homeassistant.components.motioneye.const import DEFAULT_SCAN_INTERVAL
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType
import homeassistant.util.dt as dt_util

from . import (
    TEST_CAMERA_ENTITY_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    TEST_USERNAME,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


async def test_setup_camera(hass: HomeAssistantType) -> None:
    """Test a basic camera."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"
    assert entity_state.attributes.get("friendly_name") == TEST_CAMERA_NAME


async def test_setup_camera_auth_fail(hass: HomeAssistantType) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientInvalidAuth)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_client_error(hass: HomeAssistantType) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_client_login = AsyncMock(side_effect=MotionEyeClientError)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_empty_data(hass: HomeAssistantType) -> None:
    """Test a successful camera."""
    client = create_mock_motioneye_client()
    client.async_get_cameras = AsyncMock(return_value={})
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_bad_data(hass: HomeAssistantType) -> None:
    """Test bad camera data."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    del cameras[KEY_CAMERAS][0][KEY_NAME]

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_without_streaming(hass: HomeAssistantType) -> None:
    """Test a camera without streaming enabled."""
    client = create_mock_motioneye_client()
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras[KEY_CAMERAS][0][KEY_VIDEO_STREAMING] = False

    client.async_get_cameras = AsyncMock(return_value=cameras)
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_new_data_same(hass: HomeAssistantType) -> None:
    """Test a data refresh with the same data."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_new_data_camera_removed(hass: HomeAssistantType) -> None:
    """Test a data refresh with a removed camera."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    client.async_get_cameras = AsyncMock(return_value={KEY_CAMERAS: []})
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    assert not hass.states.get(TEST_CAMERA_ENTITY_ID)


async def test_setup_camera_new_data_error(hass: HomeAssistantType) -> None:
    """Test a data refresh that fails."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    client.async_get_cameras = AsyncMock(side_effect=MotionEyeClientError)
    async_fire_time_changed(hass, dt_util.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state.state == "unavailable"


async def test_unload_camera(hass: HomeAssistantType) -> None:
    """Test unloading camera."""
    client = create_mock_motioneye_client()
    entry = await setup_mock_motioneye_config_entry(hass, client=client)
    assert hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert not client.async_client_close.called
    await hass.config_entries.async_unload(entry.entry_id)
    assert client.async_client_close.called


async def test_get_still_image_from_camera(
    aiohttp_server: Any, hass: HomeAssistantType
) -> None:
    """Test getting a still image."""

    async def verify_arguments(request: web.Request) -> web.Response:
        assert request.query == {
            "_username": TEST_USERNAME,
            "_signature": "13c528cd3178756eaf70552ac58eb0468a93aecd",
        }

    image_handler = Mock(side_effect=verify_arguments)

    app = web.Application()
    app.add_routes(
        [
            web.get(
                "/picture/100/current/",
                image_handler,
            )
        ]
    )

    server = await aiohttp_server(app)
    client = create_mock_motioneye_client()
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_HOST: "localhost",
            CONF_PORT: server.port,
            CONF_USERNAME: TEST_USERNAME,
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


async def test_get_stream_from_camera(
    aiohttp_server: Any, hass: HomeAssistantType
) -> None:
    """Test getting a stream."""

    stream_handler = Mock()
    app = web.Application()
    app.add_routes([web.get("/", stream_handler)])
    stream_server = await aiohttp_server(app)

    client = create_mock_motioneye_client()
    config_entry = create_mock_motioneye_config_entry(
        hass,
        data={
            CONF_HOST: "localhost",
            # The port won't be used as the client is a mock.
            CONF_PORT: 0,
            CONF_USERNAME: TEST_USERNAME,
        },
    )
    cameras = copy.deepcopy(TEST_CAMERAS)
    cameras["cameras"][0]["streaming_port"] = stream_server.port
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
