"""The tests for the openalpr local platform."""
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

import homeassistant.components.image_processing as ip
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_capture_events, load_fixture
from tests.components.image_processing import common


@pytest.fixture
async def setup_openalpr_local(hass):
    """Set up openalpr local."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_local",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "region": "eu",
        },
        "camera": {"platform": "demo"},
    }

    with patch(
        "homeassistant.components.openalpr_local.image_processing."
        "OpenAlprLocalEntity.should_poll",
        new_callable=PropertyMock(return_value=False),
    ):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


@pytest.fixture
def url(hass, setup_openalpr_local):
    """Return the camera URL."""
    state = hass.states.get("camera.demo_camera")
    return f"{hass.config.internal_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"


@pytest.fixture
async def alpr_events(hass):
    """Listen for events."""
    return async_capture_events(hass, "image_processing.found_plate")


@pytest.fixture
def popen_mock():
    """Get a Popen mock back."""
    async_popen = MagicMock()

    async def communicate(input=None):
        """Communicate mock."""
        fixture = bytes(load_fixture("alpr_stdout.txt"), "utf-8")
        return (fixture, None)

    async_popen.communicate = communicate

    with patch("asyncio.create_subprocess_exec", return_value=async_popen) as mock:
        yield mock


async def test_setup_platform(hass):
    """Set up platform with one entity."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_local",
            "source": {"entity_id": "camera.demo_camera"},
            "region": "eu",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.openalpr_demo_camera")


async def test_setup_platform_name(hass):
    """Set up platform with one entity and set name."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_local",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "region": "eu",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.test_local")


async def test_setup_platform_without_region(hass):
    """Set up platform with one entity without region."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_local",
            "source": {"entity_id": "camera.demo_camera"},
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(0, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


async def test_openalpr_process_image(
    setup_openalpr_local,
    url,
    hass,
    alpr_events,
    popen_mock,
    aioclient_mock,
):
    """Set up and scan a picture and test plates from event."""
    aioclient_mock.get(url, content=b"image")

    common.async_scan(hass, entity_id="image_processing.test_local")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test_local")

    assert popen_mock.called
    assert len(alpr_events) == 5
    assert state.attributes.get("vehicles") == 1
    assert state.state == "PE3R2X"

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "PE3R2X"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "PE3R2X"
    assert event_data[0]["confidence"] == float(98.9371)
    assert event_data[0]["entity_id"] == "image_processing.test_local"
