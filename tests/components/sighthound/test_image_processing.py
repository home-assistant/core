"""Tests for the Sighthound integration."""
from unittest.mock import patch

import pytest
import simplehound.core as hound

import homeassistant.components.image_processing as ip
import homeassistant.components.sighthound.image_processing as sh
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

VALID_CONFIG = {
    ip.DOMAIN: {
        "platform": "sighthound",
        CONF_API_KEY: "abc123",
        ip.CONF_SOURCE: {ip.CONF_ENTITY_ID: "camera.demo_camera"},
    },
    "camera": {"platform": "demo"},
}

VALID_ENTITY_ID = "image_processing.sighthound_demo_camera"

MOCK_DETECTIONS = {
    "image": {"width": 960, "height": 480, "orientation": 1},
    "objects": [
        {
            "type": "person",
            "boundingBox": {"x": 227, "y": 133, "height": 245, "width": 125},
        },
        {
            "type": "person",
            "boundingBox": {"x": 833, "y": 137, "height": 268, "width": 93},
        },
    ],
    "requestId": "545cec700eac4d389743e2266264e84b",
}


@pytest.fixture
def mock_detections():
    """Return a mock detection."""
    with patch(
        "simplehound.core.cloud.detect", return_value=MOCK_DETECTIONS
    ) as detection:
        yield detection


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with patch(
        "homeassistant.components.demo.camera.DemoCamera.camera_image",
        return_value=b"Test",
    ) as image:
        yield image


async def test_bad_api_key(hass, caplog):
    """Catch bad api key."""
    with patch("simplehound.core.cloud.detect", side_effect=hound.SimplehoundException):
        await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
        assert "Sighthound error" in caplog.text
        assert not hass.states.get(VALID_ENTITY_ID)


async def test_setup_platform(hass, mock_detections):
    """Set up platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass, mock_image, mock_detections):
    """Process an image."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    person_events = []

    @callback
    def capture_person_event(event):
        """Mock event."""
        person_events.append(event)

    hass.bus.async_listen(sh.EVENT_PERSON_DETECTED, capture_person_event)

    data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
    await hass.services.async_call(ip.DOMAIN, ip.SERVICE_SCAN, service_data=data)
    await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == "2"
    assert len(person_events) == 2
