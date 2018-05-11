"""The tests for the facebox component."""
from unittest.mock import patch

import pytest
import requests
import requests_mock

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_ENTITY_ID, CONF_FRIENDLY_NAME,
    CONF_IP_ADDRESS, CONF_PORT, STATE_UNKNOWN)
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.image_processing.facebox as fb

MOCK_IP = '192.168.0.1'
MOCK_PORT = '8080'

MOCK_FACE = {'confidence': 0.5812028911604818,
             'id': 'john.jpg',
             'matched': True,
             'name': 'John Lennon',
             'rect': {'height': 75, 'left': 63, 'top': 262, 'width': 74}
             }

MOCK_JSON = {"facesCount": 1,
             "success": True,
             "faces": [MOCK_FACE]
             }

VALID_ENTITY_ID = 'image_processing.facebox_demo_camera'
VALID_CONFIG = {
    ip.DOMAIN: {
        'platform': 'facebox',
        CONF_IP_ADDRESS: MOCK_IP,
        CONF_PORT: MOCK_PORT,
        ip.CONF_SOURCE: {
            ip.CONF_ENTITY_ID: 'camera.demo_camera'}
        },
    'camera': {
        'platform': 'demo'
        }
    }


def test_encode_image():
    """Test that binary data is encoded correctly."""
    assert fb.encode_image(b'test')["base64"] == 'dGVzdA=='


def test_get_matched_faces():
    """Test that matched faces are parsed correctly."""
    assert fb.get_matched_faces([MOCK_FACE]) == {MOCK_FACE['name']: 0.58}


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
               return_value=b'Test') as image:
        yield image


async def test_setup_platform(hass):
    """Setup platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass, mock_image):
    """Test processing of an image."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    face_events = []

    @callback
    def mock_face_event(event):
        """Mock event."""
        face_events.append(event)

    hass.bus.async_listen('image_processing.detect_face', mock_face_event)

    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/check".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, json=MOCK_JSON)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN,
                                       ip.SERVICE_SCAN,
                                       service_data=data)
        await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == '1'
    assert state.attributes.get('matched_faces') == {MOCK_FACE['name']: 0.58}

    MOCK_FACE[ATTR_ENTITY_ID] = VALID_ENTITY_ID  # Update.
    assert state.attributes.get('faces') == [MOCK_FACE]
    assert state.attributes.get(CONF_FRIENDLY_NAME) == 'facebox demo_camera'

    assert len(face_events) == 1
    assert face_events[0].data['name'] == MOCK_FACE['name']
    assert face_events[0].data['confidence'] == MOCK_FACE['confidence']
    assert face_events[0].data['entity_id'] == VALID_ENTITY_ID


async def test_connection_error(hass, mock_image):
    """Test connection error."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/check".format(MOCK_IP, MOCK_PORT)
        mock_req.register_uri(
                'POST', url, exc=requests.exceptions.ConnectTimeout)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN,
                                       ip.SERVICE_SCAN,
                                       service_data=data)
        await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get('faces') == []
    assert state.attributes.get('matched_faces') == {}


async def test_setup_platform_with_name(hass):
    """Setup platform with one entity and a name."""
    MOCK_NAME = 'mock_name'
    NAMED_ENTITY_ID = 'image_processing.{}'.format(MOCK_NAME)

    VALID_CONFIG_NAMED = VALID_CONFIG.copy()
    VALID_CONFIG_NAMED[ip.DOMAIN][ip.CONF_SOURCE][ip.CONF_NAME] = MOCK_NAME

    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG_NAMED)
    assert hass.states.get(NAMED_ENTITY_ID)
    state = hass.states.get(NAMED_ENTITY_ID)
    assert state.attributes.get(CONF_FRIENDLY_NAME) == MOCK_NAME
