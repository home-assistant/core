"""The tests for the clarifai_general component."""
from unittest.mock import patch

from clarifai.rest import ApiError
import pytest

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_ID, CONF_FRIENDLY_NAME
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.image_processing.clarifai_general as cg

from tests.common import MockDependency


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


def _raise():
    raise ApiError


def test_encode_image():
    """Test that binary data is encoded correctly."""
    assert cg.encode_image(b'test') == b'dGVzdA=='


def test_parse_data():
    """Test parsing of raw face data, and generation of matched_faces."""
    raw_concepts = MOCK_RESPONSE['outputs'][0]['data']['concepts']
    assert cg.parse_concepts(raw_concepts) == PARSED_CONCEPTS


@MockDependency('clarifai.rest')
def test_valid_api_key(mocked_clarifai):
    """Test that the api key is validated."""
    cg.validate_api_key(MOCK_API_KEY)
    mocked_clarifai.ClarifaiApp.assert_called_with(api_key=MOCK_API_KEY)


@MockDependency('clarifai')
@MockDependency('clarifai.rest')
@patch('clarifai.rest.ClarifaiApp', side_effect=_raise())
def test_invalid_api_key(mocked_clarifai, mocked_rest, caplog): #
    """Test that an invalid api key is caught."""
    with pytest.raises(ApiError):
        cg.validate_api_key(MOCK_API_KEY)
        #assert "Clarifai error: API Key not found" in caplog.text
