"""Tests for the Sighthound integration."""
from copy import deepcopy
import datetime
import os
from pathlib import Path
from unittest import mock

from PIL import UnidentifiedImageError
import pytest
import simplehound.core as hound

import homeassistant.components.image_processing as ip
import homeassistant.components.sighthound.image_processing as sh
from homeassistant.const import ATTR_ENTITY_ID, CONF_API_KEY
from homeassistant.core import callback
from homeassistant.setup import async_setup_component

TEST_DIR = os.path.dirname(__file__)

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

MOCK_NOW = datetime.datetime(2020, 2, 20, 10, 5, 3)


@pytest.fixture
def mock_detections():
    """Return a mock detection."""
    with mock.patch(
        "simplehound.core.cloud.detect", return_value=MOCK_DETECTIONS
    ) as detection:
        yield detection


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with mock.patch(
        "homeassistant.components.demo.camera.DemoCamera.camera_image",
        return_value=b"Test",
    ) as image:
        yield image


@pytest.fixture
def mock_bad_image_data():
    """Mock bad image data."""
    with mock.patch(
        "homeassistant.components.sighthound.image_processing.Image.open",
        side_effect=UnidentifiedImageError,
    ) as bad_data:
        yield bad_data


@pytest.fixture
def mock_now():
    """Return a mock now datetime."""
    with mock.patch("homeassistant.util.dt.now", return_value=MOCK_NOW) as now_dt:
        yield now_dt


async def test_bad_api_key(hass, caplog):
    """Catch bad api key."""
    with mock.patch(
        "simplehound.core.cloud.detect", side_effect=hound.SimplehoundException
    ):
        await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
        await hass.async_block_till_done()
        assert "Sighthound error" in caplog.text
        assert not hass.states.get(VALID_ENTITY_ID)


async def test_setup_platform(hass, mock_detections):
    """Set up platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass, mock_image, mock_detections):
    """Process an image."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    await hass.async_block_till_done()
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


async def test_catch_bad_image(
    hass, caplog, mock_image, mock_detections, mock_bad_image_data
):
    """Process an image."""
    valid_config_save_file = deepcopy(VALID_CONFIG)
    valid_config_save_file[ip.DOMAIN].update({sh.CONF_SAVE_FILE_FOLDER: TEST_DIR})
    await async_setup_component(hass, ip.DOMAIN, valid_config_save_file)
    await hass.async_block_till_done()
    assert hass.states.get(VALID_ENTITY_ID)

    data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
    await hass.services.async_call(ip.DOMAIN, ip.SERVICE_SCAN, service_data=data)
    await hass.async_block_till_done()
    assert "Sighthound unable to process image" in caplog.text


async def test_save_image(hass, mock_image, mock_detections):
    """Save a processed image."""
    valid_config_save_file = deepcopy(VALID_CONFIG)
    valid_config_save_file[ip.DOMAIN].update({sh.CONF_SAVE_FILE_FOLDER: TEST_DIR})
    await async_setup_component(hass, ip.DOMAIN, valid_config_save_file)
    await hass.async_block_till_done()
    assert hass.states.get(VALID_ENTITY_ID)

    with mock.patch(
        "homeassistant.components.sighthound.image_processing.Image.open"
    ) as pil_img_open:
        pil_img = pil_img_open.return_value
        pil_img = pil_img.convert.return_value
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN, ip.SERVICE_SCAN, service_data=data)
        await hass.async_block_till_done()
        state = hass.states.get(VALID_ENTITY_ID)
        assert state.state == "2"
        assert pil_img.save.call_count == 1

        directory = Path(TEST_DIR)
        latest_save_path = directory / "sighthound_demo_camera_latest.jpg"
        assert pil_img.save.call_args_list[0] == mock.call(latest_save_path)


async def test_save_timestamped_image(hass, mock_image, mock_detections, mock_now):
    """Save a processed image."""
    valid_config_save_ts_file = deepcopy(VALID_CONFIG)
    valid_config_save_ts_file[ip.DOMAIN].update({sh.CONF_SAVE_FILE_FOLDER: TEST_DIR})
    valid_config_save_ts_file[ip.DOMAIN].update({sh.CONF_SAVE_TIMESTAMPTED_FILE: True})
    await async_setup_component(hass, ip.DOMAIN, valid_config_save_ts_file)
    await hass.async_block_till_done()
    assert hass.states.get(VALID_ENTITY_ID)

    with mock.patch(
        "homeassistant.components.sighthound.image_processing.Image.open"
    ) as pil_img_open:
        pil_img = pil_img_open.return_value
        pil_img = pil_img.convert.return_value
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN, ip.SERVICE_SCAN, service_data=data)
        await hass.async_block_till_done()
        state = hass.states.get(VALID_ENTITY_ID)
        assert state.state == "2"
        assert pil_img.save.call_count == 2

        directory = Path(TEST_DIR)
        timestamp_save_path = (
            directory / "sighthound_demo_camera_2020-02-20_10:05:03.jpg"
        )
        assert pil_img.save.call_args_list[1] == mock.call(timestamp_save_path)
