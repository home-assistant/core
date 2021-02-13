"""Tests for the Hyperion integration."""
import asyncio
import base64
import logging
from typing import Awaitable, Callable, Optional
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    async_get_image,
    async_get_mjpeg_stream,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    async_call_registered_callback,
    create_mock_client,
    setup_test_config_entry,
)

_LOGGER = logging.getLogger(__name__)
TEST_CAMERA_ENTITY_ID = "camera.test_instance_1"
TEST_IMAGE_DATA = "TEST DATA"
TEST_IMAGE_UPDATE = {
    "command": "ledcolors-imagestream-update",
    "result": {
        "image": "data:image/jpg;base64,"
        + base64.b64encode(TEST_IMAGE_DATA.encode()).decode("ascii"),
    },
    "success": True,
}


async def test_camera_setup(hass: HomeAssistantType) -> None:
    """Test turning the light on."""
    client = create_mock_client()

    await setup_test_config_entry(hass, hyperion_client=client)

    # Verify switch is on (as per TEST_COMPONENTS above).
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"


async def test_camera_image(hass: HomeAssistantType) -> None:
    """Test retrieving a single camera image."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=True)
    client.async_send_image_stream_stop = AsyncMock(return_value=True)

    await setup_test_config_entry(hass, hyperion_client=client)

    get_image_coro = async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=None)  # type: ignore[no-untyped-call]
    image_stream_update_coro = async_call_registered_callback(
        client, "ledcolors-imagestream-update", TEST_IMAGE_UPDATE
    )
    result = await asyncio.gather(get_image_coro, image_stream_update_coro)

    assert client.async_send_image_stream_start.called
    assert client.async_send_image_stream_stop.called
    assert result[0].content == TEST_IMAGE_DATA.encode()


async def test_camera_stream(hass: HomeAssistantType) -> None:
    """Test retrieving a camera stream."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=True)
    client.async_send_image_stream_stop = AsyncMock(return_value=True)

    request = Mock()

    async def fake_get_still_stream(
        in_request: web.Request,
        callback: Callable[[], Awaitable[Optional[bytes]]],
        content_type: str,
        interval: float,
    ) -> Optional[bytes]:
        assert request == in_request
        assert content_type == DEFAULT_CONTENT_TYPE
        assert interval == 0.0
        return await callback()

    await setup_test_config_entry(hass, hyperion_client=client)

    with patch(
        "homeassistant.components.hyperion.camera.async_get_still_stream",
    ) as fake:
        fake.side_effect = fake_get_still_stream

        get_stream_coro = async_get_mjpeg_stream(hass, request, TEST_CAMERA_ENTITY_ID)  # type: ignore[no-untyped-call]
        image_stream_update_coro = async_call_registered_callback(
            client, "ledcolors-imagestream-update", TEST_IMAGE_UPDATE
        )
        result = await asyncio.gather(get_stream_coro, image_stream_update_coro)

    assert client.async_send_image_stream_start.called
    assert client.async_send_image_stream_stop.called
    assert result[0] == TEST_IMAGE_DATA.encode()
