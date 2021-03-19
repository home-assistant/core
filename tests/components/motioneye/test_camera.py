"""Test the motionEye camera."""
import copy
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock

from aiohttp import web  # type: ignore
from aiohttp.web_exceptions import HTTPBadGateway
import pytest

from homeassistant.components.camera import async_get_image, async_get_mjpeg_stream
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_USERNAME
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    TEST_CAMERA_ENTITY_ID,
    TEST_CAMERA_NAME,
    TEST_CAMERAS,
    TEST_USERNAME,
    create_mock_motioneye_client,
    create_mock_motioneye_config_entry,
    setup_mock_motioneye_config_entry,
)

_LOGGER = logging.getLogger(__name__)


async def test_setup_camera(hass: HomeAssistantType) -> None:
    """Test a basic camera."""
    client = create_mock_motioneye_client()
    await setup_mock_motioneye_config_entry(hass, client=client)

    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"
    assert entity_state.attributes.get("friendly_name") == TEST_CAMERA_NAME


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
