"""The tests for the openalpr cloud platform."""

from unittest.mock import PropertyMock, patch

import pytest

from homeassistant.components import camera, image_processing as ip
from homeassistant.components.openalpr_cloud.image_processing import OPENALPR_API_URL
from homeassistant.core import Event, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import (
    assert_setup_component,
    async_capture_events,
    async_load_fixture,
)
from tests.components.image_processing import common
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant) -> None:
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
async def setup_openalpr_cloud(hass: HomeAssistant) -> None:
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
async def setup_openalpr_cloud_vehicle_details(hass: HomeAssistant) -> None:
    """Set up openalpr cloud with vehicle details enabled."""
    config = {
        ip.DOMAIN: {
            "platform": "openalpr_cloud",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "region": "eu",
            "api_key": "sk_abcxyz123456",
            "vehicle_details": True,
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
async def alpr_events(hass: HomeAssistant) -> list[Event]:
    """Listen for events."""
    return async_capture_events(hass, "image_processing.found_plate")


PARAMS = {
    "secret_key": "sk_abcxyz123456",
    "tasks": "plate",
    "return_image": 0,
    "country": "eu",
}

PARAMS_VEHICLE = {
    "secret_key": "sk_abcxyz123456",
    "tasks": "plate,color,make,makemodel",
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
        text=await async_load_fixture(hass, "alpr_cloud.json", "openalpr_cloud"),
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
    assert "vehicle_details" not in state.attributes
    assert "manufacturer" not in state.attributes

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "H786P0J"
    ]
    assert len(event_data) == 1
    assert event_data[0]["plate"] == "H786P0J"
    assert event_data[0]["confidence"] == 90.436699
    assert event_data[0]["entity_id"] == "image_processing.test_local"
    assert "manufacturer" not in event_data[0]


async def test_openalpr_process_image_with_vehicle_details(
    alpr_events,
    setup_openalpr_cloud_vehicle_details,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Set up and scan a picture with vehicle details enabled."""
    aioclient_mock.post(
        OPENALPR_API_URL,
        params=PARAMS_VEHICLE,
        text=await async_load_fixture(
            hass, "alpr_cloud_vehicle.json", "openalpr_cloud"
        ),
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
    assert state.state == "H786P0J"
    assert state.attributes.get("color") == "Silver"
    assert state.attributes.get("manufacturer") == "Toyota"
    assert state.attributes.get("model") == "Camry"
    assert state.attributes.get("vehicle_details") == [
        {
            "plate": "H786P0J",
            "confidence": 90.436699,
            "color": "Silver",
            "manufacturer": "Toyota",
            "model": "Camry",
        }
    ]

    event_data = [
        event.data for event in alpr_events if event.data.get("plate") == "H786P0J"
    ]
    assert len(event_data) == 1
    assert event_data[0]["color"] == "Silver"
    assert event_data[0]["manufacturer"] == "Toyota"
    assert event_data[0]["model"] == "Camry"


async def test_openalpr_process_image_with_vehicle_details_low_confidence(
    alpr_events,
    setup_openalpr_cloud_vehicle_details,
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Vehicle attributes at 0 confidence are treated as no detection."""
    aioclient_mock.post(
        OPENALPR_API_URL,
        params=PARAMS_VEHICLE,
        text=await async_load_fixture(
            hass, "alpr_cloud_vehicle_low_confidence.json", "openalpr_cloud"
        ),
        status=200,
    )

    with patch(
        "homeassistant.components.camera.async_get_image",
        return_value=camera.Image("image/jpeg", b"image"),
    ):
        common.async_scan(hass, entity_id="image_processing.test_local")
        await hass.async_block_till_done()

    state = hass.states.get("image_processing.test_local")

    assert state.state == "H786P0J"
    assert "color" in state.attributes
    assert state.attributes["color"] is None
    assert "manufacturer" in state.attributes
    assert state.attributes["manufacturer"] is None
    assert "model" in state.attributes
    assert state.attributes["model"] is None
    assert state.attributes.get("vehicle_details") == [
        {
            "plate": "H786P0J",
            "confidence": 90.436699,
            "color": None,
            "manufacturer": None,
            "model": None,
        }
    ]


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
