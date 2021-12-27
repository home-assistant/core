"""The tests for the image_processing component."""
from unittest.mock import PropertyMock, patch

import pytest

import homeassistant.components.http as http
import homeassistant.components.image_processing as ip
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.exceptions import HomeAssistantError
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_capture_events
from tests.components.image_processing import common


@pytest.fixture
def aiohttp_unused_port(loop, aiohttp_unused_port, socket_enabled):
    """Return aiohttp_unused_port and allow opening sockets."""
    return aiohttp_unused_port


def get_url(hass):
    """Return camera url."""
    state = hass.states.get("camera.demo_camera")
    return f"{hass.config.internal_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"


async def setup_image_processing(hass, aiohttp_unused_port):
    """Set up things to be run when tests are started."""
    await async_setup_component(
        hass,
        http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: aiohttp_unused_port()}},
    )

    config = {ip.DOMAIN: {"platform": "test"}, "camera": {"platform": "demo"}}

    await async_setup_component(hass, ip.DOMAIN, config)
    await hass.async_block_till_done()


async def setup_image_processing_alpr(hass):
    """Set up things to be run when tests are started."""
    config = {ip.DOMAIN: {"platform": "demo"}, "camera": {"platform": "demo"}}

    await async_setup_component(hass, ip.DOMAIN, config)
    await hass.async_block_till_done()

    return async_capture_events(hass, "image_processing.found_plate")


async def setup_image_processing_face(hass):
    """Set up things to be run when tests are started."""
    config = {ip.DOMAIN: {"platform": "demo"}, "camera": {"platform": "demo"}}

    await async_setup_component(hass, ip.DOMAIN, config)
    await hass.async_block_till_done()

    return async_capture_events(hass, "image_processing.detect_face")


async def test_setup_component(hass):
    """Set up demo platform on image_process component."""
    config = {ip.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, ip.DOMAIN):
        assert await async_setup_component(hass, ip.DOMAIN, config)


async def test_setup_component_with_service(hass):
    """Set up demo platform on image_process component test service."""
    config = {ip.DOMAIN: {"platform": "demo"}}

    with assert_setup_component(1, ip.DOMAIN):
        assert await async_setup_component(hass, ip.DOMAIN, config)

    assert hass.services.has_service(ip.DOMAIN, "scan")


@patch(
    "homeassistant.components.demo.camera.Path.read_bytes",
    return_value=b"Test",
)
async def test_get_image_from_camera(
    mock_camera_read, hass, aiohttp_unused_port, enable_custom_integrations
):
    """Grab an image from camera entity."""
    await setup_image_processing(hass, aiohttp_unused_port)

    common.async_scan(hass, entity_id="image_processing.test")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test")

    assert mock_camera_read.called
    assert state.state == "1"
    assert state.attributes["image"] == b"Test"


@patch(
    "homeassistant.components.camera.async_get_image",
    side_effect=HomeAssistantError(),
)
async def test_get_image_without_exists_camera(
    mock_image, hass, aiohttp_unused_port, enable_custom_integrations
):
    """Try to get image without exists camera."""
    await setup_image_processing(hass, aiohttp_unused_port)

    hass.states.async_remove("camera.demo_camera")

    common.async_scan(hass, entity_id="image_processing.test")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test")

    assert mock_image.called
    assert state.state == "0"


async def test_alpr_event_single_call(hass, aioclient_mock):
    """Set up and scan a picture and test plates from event."""
    alpr_events = await setup_image_processing_alpr(hass)
    aioclient_mock.get(get_url(hass), content=b"image")

    common.async_scan(hass, entity_id="image_processing.demo_alpr")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.demo_alpr")

    assert len(alpr_events) == 4
    assert state.state == "AC3829"

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "AC3829"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "AC3829"
    assert event_data[0]["confidence"] == 98.3
    assert event_data[0]["entity_id"] == "image_processing.demo_alpr"


async def test_alpr_event_double_call(hass, aioclient_mock):
    """Set up and scan a picture and test plates from event."""
    alpr_events = await setup_image_processing_alpr(hass)
    aioclient_mock.get(get_url(hass), content=b"image")

    common.async_scan(hass, entity_id="image_processing.demo_alpr")
    common.async_scan(hass, entity_id="image_processing.demo_alpr")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.demo_alpr")

    assert len(alpr_events) == 4
    assert state.state == "AC3829"

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "AC3829"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "AC3829"
    assert event_data[0]["confidence"] == 98.3
    assert event_data[0]["entity_id"] == "image_processing.demo_alpr"


@patch(
    "homeassistant.components.demo.image_processing.DemoImageProcessingAlpr.confidence",
    new_callable=PropertyMock(return_value=95),
)
async def test_alpr_event_single_call_confidence(confidence_mock, hass, aioclient_mock):
    """Set up and scan a picture and test plates from event."""
    alpr_events = await setup_image_processing_alpr(hass)
    aioclient_mock.get(get_url(hass), content=b"image")

    common.async_scan(hass, entity_id="image_processing.demo_alpr")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.demo_alpr")

    assert len(alpr_events) == 2
    assert state.state == "AC3829"

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "AC3829"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "AC3829"
    assert event_data[0]["confidence"] == 98.3
    assert event_data[0]["entity_id"] == "image_processing.demo_alpr"


async def test_face_event_call(hass, aioclient_mock):
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
    "homeassistant.components.demo.image_processing."
    "DemoImageProcessingFace.confidence",
    new_callable=PropertyMock(return_value=None),
)
async def test_face_event_call_no_confidence(mock_config, hass, aioclient_mock):
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
