"""The tests for the openalpr cloud platform."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import camera, image_processing as ip
from homeassistant.components.openalpr_cloud.image_processing import OPENALPR_API_URL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, async_capture_events, load_fixture
from tests.components.image_processing import common
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
async def setup_openalpr_cloud(hass):
    """Set up openalpr cloud."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "region": "eu",
            "api_key": "sk_abcxyz123456",
        },
        "camera": {"platform": "demo"},
    }

    with patch(
        "homeassistant.components.openalpr_cloud.image_processing."
        "OpenAlprCloudEntity.should_poll",
        new_callable=PropertyMock(return_value=False),
    ):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


@pytest.fixture
async def alpr_events(hass):
    """Listen for events."""
    return async_capture_events(hass, "image_processing.found_plate")


PARAMS = {
    "secret_key": "sk_abcxyz123456",
    "tasks": "plate",
    "return_image": 0,
    "country": "eu",
}


async def test_setup_platform(hass: HomeAssistant) -> None:
    """Set up platform with one entity."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera"},
            "region": "eu",
            "api_key": "sk_abcxyz123456",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.openalpr_demo_camera")


async def test_setup_platform_name(hass: HomeAssistant) -> None:
    """Set up platform with one entity and set name."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "region": "eu",
            "api_key": "sk_abcxyz123456",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.test_local")


async def test_setup_platform_without_api_key(hass: HomeAssistant) -> None:
    """Set up platform with one entity without api_key."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera"},
            "region": "eu",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(0, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


async def test_setup_platform_without_region(hass: HomeAssistant) -> None:
    """Set up platform with one entity without region."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera"},
            "api_key": "sk_abcxyz123456",
        },
        "camera": {"platform": "demo"},
    }

    with assert_setup_component(0, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()


async def test_openalpr_process_image(
    alpr_events,
    setup_openalpr_cloud,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up and scan a picture and test plates from event."""
    aioclient_mock.post(
        OPENALPR_API_URL,
        params=PARAMS,
        text=load_fixture("alpr_cloud.json", "openalpr_cloud"),
        status=200,
    )

    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"image"),
    ):
        common.async_scan(hass, entity_id="image_processing.test_local")
        await hass.async_block_till_done()

    state = hass.states.get("image_processing.test_local")

    assert len(aioclient_mock.mock_calls) == 1
    assert len(alpr_events) == 5
    assert state.attributes.get("vehicles") == 1
    assert state.state == "H786P0J"

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "H786P0J"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "H786P0J"
    assert event_data[0]["confidence"] == 90.436699
    assert event_data[0]["entity_id"] == "image_processing.test_local"


async def test_openalpr_process_image_api_error(
    alpr_events,
    setup_openalpr_cloud,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up and scan a picture and test api error."""
    aioclient_mock.post(
        OPENALPR_API_URL,
        params=PARAMS,
        text="{'error': 'error message'}",
        status=400,
    )

    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"image"),
    ):
        common.async_scan(hass, entity_id="image_processing.test_local")
        await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(alpr_events) == 0


async def test_openalpr_process_image_api_timeout(
    alpr_events,
    setup_openalpr_cloud,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up and scan a picture and test api error."""
    aioclient_mock.post(OPENALPR_API_URL, params=PARAMS, exc=TimeoutError())

    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"image"),
    ):
        common.async_scan(hass, entity_id="image_processing.test_local")
        await hass.async_block_till_done()

    assert len(aioclient_mock.mock_calls) == 1
    assert len(alpr_events) == 0
