"""The tests for the clarifai_general component."""
from unittest.mock import patch

import pytest

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_ID, CONF_FRIENDLY_NAME
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.image_processing.clarifai_general as cg


MOCK_NAME = 'mock_name'
MOCK_API_KEY = '12345'
MOCK_KEY_ERROR = {'status': {'description': 'API key not found'}}
MOCK_RESPONSE = {'status': {'description': 'Ok'},
                 'outputs': [{'data': {'concepts': [{'name': 'dog',
                                                     'value': 0.85432},
                                                    {'name': 'cat',
                                                     'value': 0.14568}]}}]}

PARSED_CONCEPTS = {'cat': 14.57, 'dog': 85.43}

VALID_ENTITY_ID = 'image_processing.clarifai_demo_camera'
VALID_CONFIG = {
    ip.DOMAIN: {
        'platform': 'clarifai_general',
        cg.CONF_API_KEY: MOCK_API_KEY,
        ip.CONF_SOURCE: {
            ip.CONF_ENTITY_ID: 'camera.demo_camera'},
        cg.CONF_CONCEPTS: ['dog'],
    },
    'camera': {
        'platform': 'demo'
        }
    }


class KeyErrorException(Exception):
    def __init__(self):
        self.response.content = MOCK_KEY_ERROR


@pytest.fixture
def mock_app():
    """Return a mock ClarifaiApp object."""
    with patch('clarifai.rest.ClarifaiApp') as _mock_app:
        yield _mock_app


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
               return_value=b'Test') as image:
        yield image


@pytest.fixture
def mock_response():
    """Return a mock response from Clarifai."""
    with patch('clarifai.rest.ClarifaiApp.model.predict_by_base64',
               return_value=MOCK_RESPONSE) as _mock_response:
        yield _mock_response


def test_encode_image():
    """Test that binary data is encoded correctly."""
    assert cg.encode_image(b'test') == b'dGVzdA=='


def test_parse_data():
    """Test parsing of raw face data, and generation of matched_faces."""
    raw_concepts = MOCK_RESPONSE['outputs'][0]['data']['concepts']
    assert cg.parse_concepts(raw_concepts) == PARSED_CONCEPTS


def test_valid_api_key(mock_app):
    """Test that the api key is validated."""
    cg.validate_api_key(MOCK_API_KEY)
    mock_app.assert_called_with(api_key=MOCK_API_KEY)


def test_invalid_api_key(caplog, mock_app):
    """Test that an invalid api key is caught."""
    with pytest.raises(KeyErrorException):
        cg.validate_api_key(MOCK_API_KEY)
        assert "Clarifai error: API Key not found" in caplog.text


async def test_setup_platform(hass, mock_app, mock_image):
    """Set up platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass, mock_app, mock_image, mock_response):
    """Test successful processing of an image."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    events = []

    @callback
    def mock_event(event):
        """Mock event."""
        events.append(event)

    hass.bus.async_listen('image_processing.model_prediction', mock_event)
    data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
    await hass.services.async_call(ip.DOMAIN,
                                   ip.SERVICE_SCAN,
                                   service_data=data)
    await hass.async_block_till_done()


async def test_setup_platform_with_name(hass, mock_app):
    """Set up platform with one entity and a name."""
    named_entity_id = 'image_processing.{}'.format(MOCK_NAME)

    valid_config_named = VALID_CONFIG.copy()
    valid_config_named[ip.DOMAIN][ip.CONF_SOURCE][ip.CONF_NAME] = MOCK_NAME

    await async_setup_component(hass, ip.DOMAIN, valid_config_named)
    assert hass.states.get(named_entity_id)
    state = hass.states.get(named_entity_id)
    assert state.attributes.get(CONF_FRIENDLY_NAME) == MOCK_NAME

