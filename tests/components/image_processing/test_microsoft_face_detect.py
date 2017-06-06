"""The tests for the microsoft face detect platform."""
from unittest.mock import patch, PropertyMock

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.setup import setup_component
import homeassistant.components.image_processing as ip
import homeassistant.components.microsoft_face as mf

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture, mock_coro)


class TestMicrosoftFaceDetectSetup(object):
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_setup_platform(self, store_mock):
        """Setup platform with one entity."""
        config = {
            ip.DOMAIN: {
                'platform': 'microsoft_face_detect',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
                'attributes': ['age', 'gender'],
            },
            'camera': {
                'platform': 'demo'
            },
            mf.DOMAIN: {
                'api_key': '12345678abcdef6',
            }
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.states.get(
            'image_processing.microsoftface_demo_camera')

    @patch('homeassistant.components.microsoft_face.'
           'MicrosoftFace.update_store', return_value=mock_coro())
    def test_setup_platform_name(self, store_mock):
        """Setup platform with one entity and set name."""
        config = {
            ip.DOMAIN: {
                'platform': 'microsoft_face_detect',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
            },
            'camera': {
                'platform': 'demo'
            },
            mf.DOMAIN: {
                'api_key': '12345678abcdef6',
            }
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.states.get('image_processing.test_local')


class TestMicrosoftFaceDetect(object):
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        self.config = {
            ip.DOMAIN: {
                'platform': 'microsoft_face_detect',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
                'attributes': ['age', 'gender'],
            },
            'camera': {
                'platform': 'demo'
            },
            mf.DOMAIN: {
                'api_key': '12345678abcdef6',
            }
        }

        self.endpoint_url = "https://westus.{0}".format(mf.FACE_API_URL)

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.image_processing.microsoft_face_detect.'
           'MicrosoftFaceDetectEntity.should_poll',
           new_callable=PropertyMock(return_value=False))
    def test_ms_detect_process_image(self, poll_mock, aioclient_mock):
        """Setup and scan a picture and test plates from event."""
        aioclient_mock.get(
            self.endpoint_url.format("persongroups"),
            text=load_fixture('microsoft_face_persongroups.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group1/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )
        aioclient_mock.get(
            self.endpoint_url.format("persongroups/test_group2/persons"),
            text=load_fixture('microsoft_face_persons.json')
        )

        setup_component(self.hass, ip.DOMAIN, self.config)

        state = self.hass.states.get('camera.demo_camera')
        url = "{0}{1}".format(
            self.hass.config.api.base_url,
            state.attributes.get(ATTR_ENTITY_PICTURE))

        face_events = []

        @callback
        def mock_face_event(event):
            """Mock event."""
            face_events.append(event)

        self.hass.bus.listen('image_processing.detect_face', mock_face_event)

        aioclient_mock.get(url, content=b'image')

        aioclient_mock.post(
            self.endpoint_url.format("detect"),
            text=load_fixture('microsoft_face_detect.json'),
            params={'returnFaceAttributes': "age,gender"}
        )

        ip.scan(self.hass, entity_id='image_processing.test_local')
        self.hass.block_till_done()

        state = self.hass.states.get('image_processing.test_local')

        assert len(face_events) == 1
        assert state.attributes.get('total_faces') == 1
        assert state.state == '1'

        assert face_events[0].data['age'] == 71.0
        assert face_events[0].data['gender'] == 'male'
        assert face_events[0].data['entity_id'] == \
            'image_processing.test_local'
