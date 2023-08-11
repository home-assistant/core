"""The tests for the microsoft face identify platform."""
from unittest.mock import PropertyMock, patch

import pytest

import homeassistant.components.image_processing as ip
import homeassistant.components.microsoft_face as mf
from homeassistant.const import ATTR_ENTITY_PICTURE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, load_fixture
from tests.components.image_processing import common
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.fixture(autouse=True)
async def setup_homeassistant(hass: HomeAssistant):
    """Set up the homeassistant integration."""
    await async_setup_component(hass, "homeassistant", {})


@pytest.fixture
def store_mock():
    """Mock update store."""
    with patch(
        "homeassistant.components.microsoft_face.MicrosoftFace.update_store",
        return_value=None,
    ) as mock_update_store:
        yield mock_update_store


@pytest.fixture
def poll_mock():
    """Disable polling."""
    with patch(
        "homeassistant.components.microsoft_face_identify.image_processing."
        "MicrosoftFaceIdentifyEntity.should_poll",
        new_callable=PropertyMock(return_value=False),
    ):
        yield


CONFIG = {
    ip.DOMAIN: {
        "platform": "microsoft_face_identify",
        "source": {"entity_id": "camera.demo_camera", "name": "test local"},
        "group": "Test Group1",
    },
    "camera": {"platform": "demo"},
    mf.DOMAIN: {"api_key": "12345678abcdef6"},
}

ENDPOINT_URL = f"https://westus.{mf.FACE_API_URL}"


async def test_setup_platform(hass: HomeAssistant, store_mock) -> None:
    """Set up platform with one entity."""
    config = {
        ip.DOMAIN: {
            "platform": "microsoft_face_identify",
            "source": {"entity_id": "camera.demo_camera"},
            "group": "Test Group1",
        },
        "camera": {"platform": "demo"},
        mf.DOMAIN: {"api_key": "12345678abcdef6"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.microsoftface_demo_camera")


async def test_setup_platform_name(hass: HomeAssistant, store_mock) -> None:
    """Set up platform with one entity and set name."""
    config = {
        ip.DOMAIN: {
            "platform": "microsoft_face_identify",
            "source": {"entity_id": "camera.demo_camera", "name": "test local"},
            "group": "Test Group1",
        },
        "camera": {"platform": "demo"},
        mf.DOMAIN: {"api_key": "12345678abcdef6"},
    }

    with assert_setup_component(1, ip.DOMAIN):
        await async_setup_component(hass, ip.DOMAIN, config)
        await hass.async_block_till_done()

    assert hass.states.get("image_processing.test_local")


async def test_ms_identify_process_image(
    hass: HomeAssistant, poll_mock, aioclient_mock: AiohttpClientMocker
) -> None:
    """Set up and scan a picture and test plates from event."""
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups"),
        text=load_fixture("microsoft_face_persongroups.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group1/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )
    aioclient_mock.get(
        ENDPOINT_URL.format("persongroups/test_group2/persons"),
        text=load_fixture("microsoft_face_persons.json"),
    )

    await async_setup_component(hass, ip.DOMAIN, CONFIG)
    await hass.async_block_till_done()

    state = hass.states.get("camera.demo_camera")
    url = f"{hass.config.internal_url}{state.attributes.get(ATTR_ENTITY_PICTURE)}"

    face_events = []

    @callback
    def mock_face_event(event):
        """Mock event."""
        face_events.append(event)

    hass.bus.async_listen("image_processing.detect_face", mock_face_event)

    aioclient_mock.get(url, content=b"image")

    aioclient_mock.post(
        ENDPOINT_URL.format("detect"),
        text=load_fixture("microsoft_face_detect.json"),
    )
    aioclient_mock.post(
        ENDPOINT_URL.format("identify"),
        text=load_fixture("microsoft_face_identify.json"),
    )

    common.async_scan(hass, entity_id="image_processing.test_local")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test_local")

    assert len(face_events) == 1
    assert state.attributes.get("total_faces") == 2
    assert state.state == "David"

    assert face_events[0].data["name"] == "David"
    assert face_events[0].data["confidence"] == float(92)
    assert face_events[0].data["entity_id"] == "image_processing.test_local"

    # Test that later, if a request is made that results in no face
    # being detected, that this is reflected in the state object
    aioclient_mock.clear_requests()
    aioclient_mock.post(ENDPOINT_URL.format("detect"), text="[]")

    common.async_scan(hass, entity_id="image_processing.test_local")
    await hass.async_block_till_done()

    state = hass.states.get("image_processing.test_local")

    # No more face events were fired
    assert len(face_events) == 1
    # Total faces and actual qualified number of faces reset to zero
    assert state.attributes.get("total_faces") == 0
    assert state.state == STATE_UNKNOWN
