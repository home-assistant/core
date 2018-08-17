"""The tests for the facebox component."""
from unittest.mock import Mock, mock_open, patch

import pytest
import requests
import requests_mock

from homeassistant.core import callback
from homeassistant.const import (
    ATTR_ENTITY_ID, ATTR_NAME, CONF_FRIENDLY_NAME, CONF_PASSWORD,
    CONF_USERNAME, CONF_IP_ADDRESS, CONF_PORT,
    HTTP_BAD_REQUEST, HTTP_OK, HTTP_UNAUTHORIZED, STATE_UNKNOWN)
from homeassistant.setup import async_setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.image_processing.facebox as fb

MOCK_IP = '192.168.0.1'
MOCK_PORT = '8080'

# Mock data returned by the facebox API.
MOCK_BOX_ID = 'b893cc4f7fd6'
MOCK_ERROR_NO_FACE = "No face found"
MOCK_FACE = {'confidence': 0.5812028911604818,
             'id': 'john.jpg',
             'matched': True,
             'name': 'John Lennon',
             'rect': {'height': 75, 'left': 63, 'top': 262, 'width': 74}}

MOCK_FILE_PATH = '/images/mock.jpg'

MOCK_HEALTH = {'success': True,
               'hostname': 'b893cc4f7fd6',
               'metadata': {'boxname': 'facebox', 'build': 'development'},
               'errors': []}

MOCK_JSON = {"facesCount": 1,
             "success": True,
             "faces": [MOCK_FACE]}

MOCK_NAME = 'mock_name'
MOCK_USERNAME = 'mock_username'
MOCK_PASSWORD = 'mock_password'

# Faces data after parsing.
PARSED_FACES = [{fb.FACEBOX_NAME: 'John Lennon',
                 fb.ATTR_IMAGE_ID: 'john.jpg',
                 fb.ATTR_CONFIDENCE: 58.12,
                 fb.ATTR_MATCHED: True,
                 fb.ATTR_BOUNDING_BOX: {
                     'height': 75,
                     'left': 63,
                     'top': 262,
                     'width': 74}}]

MATCHED_FACES = {'John Lennon': 58.12}

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


@pytest.fixture
def mock_healthybox():
    """Mock fb.check_box_health."""
    check_box_health = 'homeassistant.components.image_processing.' \
        'facebox.check_box_health'
    with patch(check_box_health, return_value=MOCK_BOX_ID) as _mock_healthybox:
        yield _mock_healthybox


@pytest.fixture
def mock_isfile():
    """Mock os.path.isfile."""
    with patch('homeassistant.components.image_processing.facebox.cv.isfile',
               return_value=True) as _mock_isfile:
        yield _mock_isfile


@pytest.fixture
def mock_image():
    """Return a mock camera image."""
    with patch('homeassistant.components.camera.demo.DemoCamera.camera_image',
               return_value=b'Test') as image:
        yield image


@pytest.fixture
def mock_open_file():
    """Mock open."""
    mopen = mock_open()
    with patch('homeassistant.components.image_processing.facebox.open',
               mopen, create=True) as _mock_open:
        yield _mock_open


def test_check_box_health(caplog):
    """Test check box health."""
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/healthz".format(MOCK_IP, MOCK_PORT)
        mock_req.get(url, status_code=HTTP_OK, json=MOCK_HEALTH)
        assert fb.check_box_health(url, 'user', 'pass') == MOCK_BOX_ID

        mock_req.get(url, status_code=HTTP_UNAUTHORIZED)
        assert fb.check_box_health(url, None, None) is None
        assert "AuthenticationError on facebox" in caplog.text

        mock_req.get(url, exc=requests.exceptions.ConnectTimeout)
        fb.check_box_health(url, None, None)
        assert "ConnectionError: Is facebox running?" in caplog.text


def test_encode_image():
    """Test that binary data is encoded correctly."""
    assert fb.encode_image(b'test') == 'dGVzdA=='


def test_get_matched_faces():
    """Test that matched_faces are parsed correctly."""
    assert fb.get_matched_faces(PARSED_FACES) == MATCHED_FACES


def test_parse_faces():
    """Test parsing of raw face data, and generation of matched_faces."""
    assert fb.parse_faces(MOCK_JSON['faces']) == PARSED_FACES


@patch('os.access', Mock(return_value=False))
def test_valid_file_path():
    """Test that an invalid file_path is caught."""
    assert not fb.valid_file_path('test_path')


async def test_setup_platform(hass, mock_healthybox):
    """Setup platform with one entity."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_setup_platform_with_auth(hass, mock_healthybox):
    """Setup platform with one entity and auth."""
    valid_config_auth = VALID_CONFIG.copy()
    valid_config_auth[ip.DOMAIN][CONF_USERNAME] = MOCK_USERNAME
    valid_config_auth[ip.DOMAIN][CONF_PASSWORD] = MOCK_PASSWORD

    await async_setup_component(hass, ip.DOMAIN, valid_config_auth)
    assert hass.states.get(VALID_ENTITY_ID)


async def test_process_image(hass, mock_healthybox, mock_image):
    """Test successful processing of an image."""
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
    assert state.attributes.get('matched_faces') == MATCHED_FACES
    assert state.attributes.get('total_matched_faces') == 1

    PARSED_FACES[0][ATTR_ENTITY_ID] = VALID_ENTITY_ID  # Update.
    assert state.attributes.get('faces') == PARSED_FACES
    assert state.attributes.get(CONF_FRIENDLY_NAME) == 'facebox demo_camera'

    assert len(face_events) == 1
    assert face_events[0].data[ATTR_NAME] == PARSED_FACES[0][ATTR_NAME]
    assert (face_events[0].data[fb.ATTR_CONFIDENCE]
            == PARSED_FACES[0][fb.ATTR_CONFIDENCE])
    assert face_events[0].data[ATTR_ENTITY_ID] == VALID_ENTITY_ID
    assert (face_events[0].data[fb.ATTR_IMAGE_ID] ==
            PARSED_FACES[0][fb.ATTR_IMAGE_ID])
    assert (face_events[0].data[fb.ATTR_BOUNDING_BOX] ==
            PARSED_FACES[0][fb.ATTR_BOUNDING_BOX])


async def test_process_image_errors(hass, mock_healthybox, mock_image, caplog):
    """Test process_image errors."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    # Test connection error.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/check".format(MOCK_IP, MOCK_PORT)
        mock_req.register_uri(
            'POST', url, exc=requests.exceptions.ConnectTimeout)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN,
                                       ip.SERVICE_SCAN,
                                       service_data=data)
        await hass.async_block_till_done()
        assert "ConnectionError: Is facebox running?" in caplog.text

    state = hass.states.get(VALID_ENTITY_ID)
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get('faces') == []
    assert state.attributes.get('matched_faces') == {}

    # Now test with bad auth.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/check".format(MOCK_IP, MOCK_PORT)
        mock_req.register_uri(
            'POST', url, status_code=HTTP_UNAUTHORIZED)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID}
        await hass.services.async_call(ip.DOMAIN,
                                       ip.SERVICE_SCAN,
                                       service_data=data)
        await hass.async_block_till_done()
        assert "AuthenticationError on facebox" in caplog.text


async def test_teach_service(
        hass, mock_healthybox, mock_image,
        mock_isfile, mock_open_file, caplog):
    """Test teaching of facebox."""
    await async_setup_component(hass, ip.DOMAIN, VALID_CONFIG)
    assert hass.states.get(VALID_ENTITY_ID)

    # Patch out 'is_allowed_path' as the mock files aren't allowed
    hass.config.is_allowed_path = Mock(return_value=True)

    # Test successful teach.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/teach".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, status_code=HTTP_OK)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID,
                ATTR_NAME: MOCK_NAME,
                fb.FILE_PATH: MOCK_FILE_PATH}
        await hass.services.async_call(
            ip.DOMAIN, fb.SERVICE_TEACH_FACE, service_data=data)
        await hass.async_block_till_done()

    # Now test with bad auth.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/teach".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, status_code=HTTP_UNAUTHORIZED)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID,
                ATTR_NAME: MOCK_NAME,
                fb.FILE_PATH: MOCK_FILE_PATH}
        await hass.services.async_call(ip.DOMAIN,
                                       fb.SERVICE_TEACH_FACE,
                                       service_data=data)
        await hass.async_block_till_done()
        assert "AuthenticationError on facebox" in caplog.text

    # Now test the failed teaching.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/teach".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, status_code=HTTP_BAD_REQUEST,
                      text=MOCK_ERROR_NO_FACE)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID,
                ATTR_NAME: MOCK_NAME,
                fb.FILE_PATH: MOCK_FILE_PATH}
        await hass.services.async_call(ip.DOMAIN,
                                       fb.SERVICE_TEACH_FACE,
                                       service_data=data)
        await hass.async_block_till_done()
        assert MOCK_ERROR_NO_FACE in caplog.text

    # Now test connection error.
    with requests_mock.Mocker() as mock_req:
        url = "http://{}:{}/facebox/teach".format(MOCK_IP, MOCK_PORT)
        mock_req.post(url, exc=requests.exceptions.ConnectTimeout)
        data = {ATTR_ENTITY_ID: VALID_ENTITY_ID,
                ATTR_NAME: MOCK_NAME,
                fb.FILE_PATH: MOCK_FILE_PATH}
        await hass.services.async_call(ip.DOMAIN,
                                       fb.SERVICE_TEACH_FACE,
                                       service_data=data)
        await hass.async_block_till_done()
        assert "ConnectionError: Is facebox running?" in caplog.text


async def test_setup_platform_with_name(hass, mock_healthybox):
    """Setup platform with one entity and a name."""
    named_entity_id = 'image_processing.{}'.format(MOCK_NAME)

    valid_config_named = VALID_CONFIG.copy()
    valid_config_named[ip.DOMAIN][ip.CONF_SOURCE][ip.CONF_NAME] = MOCK_NAME

    await async_setup_component(hass, ip.DOMAIN, valid_config_named)
    assert hass.states.get(named_entity_id)
    state = hass.states.get(named_entity_id)
    assert state.attributes.get(CONF_FRIENDLY_NAME) == MOCK_NAME
