"""Test ESPHome cameras."""

from collections.abc import Awaitable, Callable

from aioesphomeapi import (
    APIClient,
    CameraInfo,
    CameraState,
    EntityInfo,
    EntityState,
    UserService,
)

from homeassistant.components.camera import STATE_IDLE
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from .conftest import MockESPHomeDevice

from tests.typing import ClientSessionGenerator

SMALLEST_VALID_JPEG = (
    "ffd8ffe000104a46494600010101004800480000ffdb00430003020202020203020202030303030406040404040408060"
    "6050609080a0a090809090a0c0f0c0a0b0e0b09090d110d0e0f101011100a0c12131210130f101010ffc9000b08000100"
    "0101011100ffcc000600101005ffda0008010100003f00d2cf20ffd9"
)
SMALLEST_VALID_JPEG_BYTES = bytes.fromhex(SMALLEST_VALID_JPEG)


async def test_camera_single_image(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera single image request."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE

    def _mock_camera_image():
        mock_device.set_state(CameraState(key=1, data=SMALLEST_VALID_JPEG_BYTES))

    mock_client.request_single_image = _mock_camera_image

    client = await hass_client()
    resp = await client.get("/api/camera_proxy/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE

    assert resp.status == 200
    assert resp.content_type == "image/jpeg"
    assert resp.content_length == len(SMALLEST_VALID_JPEG_BYTES)
    assert await resp.read() == SMALLEST_VALID_JPEG_BYTES


async def test_camera_single_image_unavailable_before_requested(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera that goes unavailable before the request."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE
    await mock_device.mock_disconnect(False)

    client = await hass_client()
    resp = await client.get("/api/camera_proxy/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    assert resp.status == 500


async def test_camera_single_image_unavailable_during_request(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera that goes unavailable before the request."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE

    def _mock_camera_image():
        hass.async_create_task(mock_device.mock_disconnect(False))

    mock_client.request_single_image = _mock_camera_image

    client = await hass_client()
    resp = await client.get("/api/camera_proxy/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE

    assert resp.status == 500


async def test_camera_stream(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera stream."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE
    remaining_responses = 3

    def _mock_camera_image():
        nonlocal remaining_responses
        if remaining_responses == 0:
            return
        remaining_responses -= 1
        mock_device.set_state(CameraState(key=1, data=SMALLEST_VALID_JPEG_BYTES))

    mock_client.request_image_stream = _mock_camera_image
    mock_client.request_single_image = _mock_camera_image

    client = await hass_client()
    resp = await client.get("/api/camera_proxy_stream/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE

    assert resp.status == 200
    assert resp.content_type == "multipart/x-mixed-replace"
    assert resp.content_length is None
    raw_stream = b""
    async for data in resp.content.iter_any():
        raw_stream += data
        if len(raw_stream) > 300:
            break

    assert b"image/jpeg" in raw_stream


async def test_camera_stream_unavailable(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera stream when the device is disconnected."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE

    await mock_device.mock_disconnect(False)

    client = await hass_client()
    await client.get("/api/camera_proxy_stream/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_camera_stream_with_disconnection(
    hass: HomeAssistant,
    mock_client: APIClient,
    mock_esphome_device: Callable[
        [APIClient, list[EntityInfo], list[UserService], list[EntityState]],
        Awaitable[MockESPHomeDevice],
    ],
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a generic camera stream that goes unavailable during the request."""
    entity_info = [
        CameraInfo(
            object_id="mycamera",
            key=1,
            name="my camera",
            unique_id="my_camera",
        )
    ]
    states = []
    user_service = []
    mock_device = await mock_esphome_device(
        mock_client=mock_client,
        entity_info=entity_info,
        user_service=user_service,
        states=states,
    )
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_IDLE
    remaining_responses = 3

    def _mock_camera_image():
        nonlocal remaining_responses
        if remaining_responses == 0:
            return
        if remaining_responses == 2:
            hass.async_create_task(mock_device.mock_disconnect(False))
        remaining_responses -= 1
        mock_device.set_state(CameraState(key=1, data=SMALLEST_VALID_JPEG_BYTES))

    mock_client.request_image_stream = _mock_camera_image
    mock_client.request_single_image = _mock_camera_image

    client = await hass_client()
    await client.get("/api/camera_proxy_stream/camera.test_mycamera")
    await hass.async_block_till_done()
    state = hass.states.get("camera.test_mycamera")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
