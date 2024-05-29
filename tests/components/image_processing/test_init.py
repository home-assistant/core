"""The tests for the image_processing component."""

from asyncio import AbstractEventLoop
from collections.abc import Callable
from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import http
import homeassistant.components.image_processing as ip
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from . import common

from tests.common import assert_setup_component, async_capture_events
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def aiohttp_unused_port_factory(
    event_loop: AbstractEventLoop,
    unused_tcp_port_factory: Callable[[], int],
    socket_enabled: None,
) -> Callable[[], int]:
    """Return aiohttp_unused_port and allow opening sockets."""
    return unused_tcp_port_factory


def get_url(hass):
    """Return camera url."""
    state = hass.states.get("camera.demo_camera")
    return f"{hass.config.internal_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"


async def setup_image_processing(hass, aiohttp_unused_port_factory):
    """Set up things to be run when tests are started."""
    await async_setup_component(
        hass,
        http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: aiohttp_unused_port_factory()}},
    )

    config = {ip.DOMAIN: {"platform": "test"}, "camera": {"platform": "demo"}}

    await async_setup_component(hass, ip.DOMAIN, config)
    await hass.async_block_till_done()


async def setup_image_processing_face(hass):
    """Set up things to be run when tests are started."""
    config = {ip.DOMAIN: {"platform": "demo"}, "camera": {"platform": "demo"}}

    await async_setup_component(hass, ip.DOMAIN, config)
    await hass.async_block_till_done()

    return async_capture_events(hass, "image_processing.detect_face")


async def test_setup_component(hass: HomeAssistant) -> None:
    """Set up demo platform on image_process component."""
    config = {ip.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, ip.DOMAIN):
        assert await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_component_with_service(hass: HomeAssistant) -> None:
    """Set up demo platform on image_process component test service."""
    config = {ip.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, ip.DOMAIN):
        assert await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.services.has_service(ip.DOMAIN, "scan")


@patch(
    "homeassistant.components.demo.camera.Path.read_bytes",
    return_value=b"Test",
)
async def test_get_image_from_camera(
    mock_camera_read,
    hass: HomeAssistant,
    aiohttp_unused_port_factory,
    enable_custom_integrations: None,
) -> None:
    """Grab an image from camera entity."""
    await setup_image_processing(hass, aiohttp_unused_port_factory)

    common.async_scan(hass, entity_id="image_processing.test")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test")

    assert mock_camera_read.called
    assert state.state == "1"
    assert state.attributes["image"] == b"Test"


@patch(
    "homeassistant.components.image_processing.async_get_image",
    side_effect=HomeAssistantError(),
)
async def test_get_image_without_exists_camera(
    mock_image,
    hass: HomeAssistant,
    aiohttp_unused_port_factory,
    enable_custom_integrations: None,
) -> None:
    """Try to get image without exists camera."""
    await setup_image_processing(hass, aiohttp_unused_port_factory)

    hass.states.async_remove("camera.demo_camera")

    common.async_scan(hass, entity_id="image_processing.test")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test")

    assert mock_image.called
    assert state.state == "0"


async def test_face_event_call(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Set up and scan a picture and test faces from event."""
    face_events = await setup_image_processing_face(hass)
    aioclient_mock.get(get_url(hass), content=b"image")

    common.async_scan(hass, entity_id="image_processing.demo_face")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.demo_face")

    assert len(face_events) == 2
    assert state.state == "Hans"
    assert state.attributes["total_faces"] == 4

    event_data = [
        event.data for event in face_events if event.data.get("name") == "Hans"
    ]
    assert len(event_data) == 1
    assert event_data[0]["name"] == "Hans"
    assert event_data[0]["confidence"] == 98.34
    assert event_data[0]["gender"] == "male"
    assert event_data[0]["entity_id"] == "image_processing.demo_face"


@patch(
    "homeassistant.components.demo.image_processing.DemoImageProcessingFace.confidence",
    new_callable=PropertyMock(return_value=None),
)
async def test_face_event_call_no_confidence(
    mock_config, hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Set up and scan a picture and test faces from event."""
    face_events = await setup_image_processing_face(hass)
    aioclient_mock.get(get_url(hass), content=b"image")

    common.async_scan(hass, entity_id="image_processing.demo_face")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.demo_face")

    assert len(face_events) == 3
    assert state.state == "4"
    assert state.attributes["total_faces"] == 4

    event_data = [
        event.data for event in face_events if event.data.get("name") == "Hans"
    ]
    assert len(event_data) == 1
    assert event_data[0]["name"] == "Hans"
    assert event_data[0]["confidence"] == 98.34
    assert event_data[0]["gender"] == "male"
    assert event_data[0]["entity_id"] == "image_processing.demo_face"


async def test_update_missing_camera(
    hass: HomeAssistant,
    aiohttp_unused_port_factory,
    enable_custom_integrations: None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test when entity does not set camera."""
    await setup_image_processing(hass, aiohttp_unused_port_factory)

    with patch(
        "custom_components.test.image_processing.TestImageProcessing.camera_entity",
        new_callable=PropertyMock(return_value=None),
    ):
        common.async_scan(hass, entity_id="image_processing.test")
        await hass.async_block_till_done()

    assert "No camera entity id was set by the image processing entity" in caplog.text
