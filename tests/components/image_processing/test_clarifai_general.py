"""The tests for the clarifai_general platform."""
import json
from unittest.mock import call, patch

from clarifai.rest import ApiError
from clarifai.rest.client import Model
import pytest

from homeassistant.const import (ATTR_ENTITY_ID, CONF_FRIENDLY_NAME,
                                 STATE_UNKNOWN)
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.image_processing.clarifai_general as cg


MOCK_NAME = 'mock_name'
MOCK_API_KEY = '12345'
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
    },
    'camera': {
        'platform': 'demo'
        }
    }


class MockErrorResponse:
    """Mock Clarifai RESPONSE to bad API key."""

    status_code = 404
    reason = 'Failure'
    content = json.dumps({'status': {'description': 'API key not found'}})

    @staticmethod
    def json():
        """Handle json."""
        return {}


RESOURCE = 'https://www.mock.com/url'
PARAMS = {}
METHOD = 'GET'
RESPONSE = MockErrorResponse()
ERROR = ApiError(RESOURCE, PARAMS, METHOD, RESPONSE)


@pytest.fixture
def mock_app():
    """Return a mock ClarifaiApp object."""
    with patch('clarifai.rest.ClarifaiApp') as _mock_app:
        yield _mock_app


@pytest.fixture
def mock_app_with_error():
    """Throw an ApiError."""
    with patch('clarifai.rest.ClarifaiApp',
               side_effect=ERROR) as _mock_mock_app_with_error:
        yield _mock_mock_app_with_error


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
               return_value=b'Test') as image:
        yield image


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
    assert mock_app.call_count == 1
    assert mock_app.call_args == call(api_key=MOCK_API_KEY)


def test_invalid_api_key(mock_app_with_error, caplog):
    """Test that an invalid api key is caught."""
    assert cg.validate_api_key(MOCK_API_KEY) is None
    assert "Clarifai error: API key not found" in caplog.text


async def test_setup_platform(hass, mock_app, mock_image):
    """Set up platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


@patch.object(Model, 'predict_by_base64', return_value=MOCK_RESPONSE)
async def test_process_image(hass, mock_app, mock_image):
    """Test successful processing of an image."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
    await hass.services.async_call(ip.DOMAIN,
                                   ip.SERVICE_SCAN,
                                   service_data=data)
    await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == 'dog'
    assert state.attributes.get('dog') == PARSED_CONCEPTS['dog']


@patch.object(Model, 'predict_by_base64', side_effect=ERROR)
async def test_process_with_error(hass, mock_app, mock_image,
                                  caplog):
    """Test processing with error from predict_by_base64."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)
    data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
    await hass.services.async_call(ip.DOMAIN,
                                   ip.SERVICE_SCAN,
                                   service_data=data)
    await hass.async_block_till_done()

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert "Clarifai error: check your internet connection" in caplog.text


async def test_setup_platform_with_name(hass, mock_app):
    """Set up platform with one entity and a name."""
    named_entity_id = 'image_processing.{}'.format(MOCK_NAME)

    valid_config_named = VALID_CONFIG.copy()
    valid_config_named[ip.DOMAIN][ip.CONF_SOURCE][ip.CONF_NAME] = MOCK_NAME

    await async_setup_component(hass, ip.DOMAIN, valid_config_named)
    assert hass.states.get(named_entity_id)
    state = hass.states.get(named_entity_id)
    assert state.attributes.get(CONF_FRIENDLY_NAME) == MOCK_NAME
