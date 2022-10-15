"""Tests for the Hyperion integration."""
from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import web
import pytest

from homeassistant.components.camera import (
    DEFAULT_CONTENT_TYPE,
    DOMAIN as CAMERA_DOMAIN,
    async_get_image,
    async_get_mjpeg_stream,
)
from homeassistant.components.hyperion import get_hyperion_device_id
from homeassistant.components.hyperion.const import (
    DOMAIN,
    HYPERION_MANUFACTURER_NAME,
    HYPERION_MODEL_NAME,
    TYPE_HYPERION_CAMERA,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    TEST_CONFIG_ENTRY_ID,
    TEST_INSTANCE,
    TEST_INSTANCE_1,
    TEST_SYSINFO_ID,
    async_call_registered_callback,
    create_mock_client,
    register_test_entity,
    setup_test_config_entry,
)

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


async def test_camera_setup(hass: HomeAssistant) -> None:
    """Test turning the light on."""
    client = create_mock_client()

    await setup_test_config_entry(hass, hyperion_client=client)

    # Verify switch is on (as per TEST_COMPONENTS above).
    entity_state = hass.states.get(TEST_CAMERA_ENTITY_ID)
    assert entity_state
    assert entity_state.state == "idle"


async def test_camera_image(hass: HomeAssistant) -> None:
    """Test retrieving a single camera image."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=True)
    client.async_send_image_stream_stop = AsyncMock(return_value=True)

    await setup_test_config_entry(hass, hyperion_client=client)

    get_image_coro = async_get_image(hass, TEST_CAMERA_ENTITY_ID)
    image_stream_update_coro = async_call_registered_callback(
        client, "ledcolors-imagestream-update", TEST_IMAGE_UPDATE
    )
    result = await asyncio.gather(get_image_coro, image_stream_update_coro)

    assert client.async_send_image_stream_start.called
    assert client.async_send_image_stream_stop.called
    assert result[0].content == TEST_IMAGE_DATA.encode()


async def test_camera_invalid_image(hass: HomeAssistant) -> None:
    """Test retrieving a single invalid camera image."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=True)
    client.async_send_image_stream_stop = AsyncMock(return_value=True)

    await setup_test_config_entry(hass, hyperion_client=client)

    get_image_coro = async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=0)
    image_stream_update_coro = async_call_registered_callback(
        client, "ledcolors-imagestream-update", None
    )
    with pytest.raises(HomeAssistantError):
        await asyncio.gather(get_image_coro, image_stream_update_coro)

    get_image_coro = async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=0)
    image_stream_update_coro = async_call_registered_callback(
        client, "ledcolors-imagestream-update", {"garbage": 1}
    )
    with pytest.raises(HomeAssistantError):
        await asyncio.gather(get_image_coro, image_stream_update_coro)

    get_image_coro = async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=0)
    image_stream_update_coro = async_call_registered_callback(
        client,
        "ledcolors-imagestream-update",
        {"result": {"image": "data:image/jpg;base64,FOO"}},
    )
    with pytest.raises(HomeAssistantError):
        await asyncio.gather(get_image_coro, image_stream_update_coro)


async def test_camera_image_failed_start_stream_call(hass: HomeAssistant) -> None:
    """Test retrieving a single camera image with failed start stream call."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=False)

    await setup_test_config_entry(hass, hyperion_client=client)

    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, TEST_CAMERA_ENTITY_ID, timeout=0.01)

    assert client.async_send_image_stream_start.called
    assert not client.async_send_image_stream_stop.called


async def test_camera_stream(hass: HomeAssistant) -> None:
    """Test retrieving a camera stream."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=True)
    client.async_send_image_stream_stop = AsyncMock(return_value=True)

    request = Mock()

    async def fake_get_still_stream(
        in_request: web.Request,
        callback: Callable[[], Awaitable[bytes | None]],
        content_type: str,
        interval: float,
    ) -> bytes | None:
        assert request == in_request
        assert content_type == DEFAULT_CONTENT_TYPE
        assert interval == 0.0
        return await callback()

    await setup_test_config_entry(hass, hyperion_client=client)

    with patch(
        "homeassistant.components.hyperion.camera.async_get_still_stream",
    ) as fake:
        fake.side_effect = fake_get_still_stream

        get_stream_coro = async_get_mjpeg_stream(hass, request, TEST_CAMERA_ENTITY_ID)
        image_stream_update_coro = async_call_registered_callback(
            client, "ledcolors-imagestream-update", TEST_IMAGE_UPDATE
        )
        result = await asyncio.gather(get_stream_coro, image_stream_update_coro)

    assert client.async_send_image_stream_start.called
    assert client.async_send_image_stream_stop.called
    assert result[0] == TEST_IMAGE_DATA.encode()


async def test_camera_stream_failed_start_stream_call(hass: HomeAssistant) -> None:
    """Test retrieving a camera stream with failed start stream call."""
    client = create_mock_client()
    client.async_send_image_stream_start = AsyncMock(return_value=False)

    await setup_test_config_entry(hass, hyperion_client=client)

    request = Mock()
    assert not await async_get_mjpeg_stream(hass, request, TEST_CAMERA_ENTITY_ID)

    assert client.async_send_image_stream_start.called
    assert not client.async_send_image_stream_stop.called


async def test_device_info(hass: HomeAssistant) -> None:
    """Verify device information includes expected details."""
    client = create_mock_client()

    register_test_entity(
        hass,
        CAMERA_DOMAIN,
        TYPE_HYPERION_CAMERA,
        TEST_CAMERA_ENTITY_ID,
    )
    await setup_test_config_entry(hass, hyperion_client=client)

    device_id = get_hyperion_device_id(TEST_SYSINFO_ID, TEST_INSTANCE)
    device_registry = dr.async_get(hass)

    device = device_registry.async_get_device({(DOMAIN, device_id)})
    assert device
    assert device.config_entries == {TEST_CONFIG_ENTRY_ID}
    assert device.identifiers == {(DOMAIN, device_id)}
    assert device.manufacturer == HYPERION_MANUFACTURER_NAME
    assert device.model == HYPERION_MODEL_NAME
    assert device.name == TEST_INSTANCE_1["friendly_name"]

    entity_registry = er.async_get(hass)
    entities_from_device = [
        entry.entity_id
        for entry in er.async_entries_for_device(entity_registry, device.id)
    ]
    assert TEST_CAMERA_ENTITY_ID in entities_from_device
