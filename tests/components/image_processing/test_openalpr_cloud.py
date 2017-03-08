"""The tests for the openalpr clooud platform."""
import asyncio
from unittest.mock import patch, PropertyMock

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.setup import setup_component
import homeassistant.components.image_processing as ip
from homeassistant.components.image_processing.openalpr_cloud import (
    OPENALPR_API_URL)

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture)


class TestOpenAlprCloudlSetup(object):
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_platform(self):
        """Setup platform with one entity."""
        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_cloud',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
                'region': 'eu',
                'api_key': 'sk_abcxyz123456',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.states.get('image_processing.openalpr_demo_camera')

    def test_setup_platform_name(self):
        """Setup platform with one entity and set name."""
        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_cloud',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
                'region': 'eu',
                'api_key': 'sk_abcxyz123456',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.states.get('image_processing.test_local')

    def test_setup_platform_without_api_key(self):
        """Setup platform with one entity without api_key."""
        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_cloud',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
                'region': 'eu',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(0, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

    def test_setup_platform_without_region(self):
        """Setup platform with one entity without region."""
        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_cloud',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
                'api_key': 'sk_abcxyz123456',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(0, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)


class TestOpenAlprCloud(object):
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_cloud',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
                'region': 'eu',
                'api_key': 'sk_abcxyz123456',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with patch('homeassistant.components.image_processing.openalpr_cloud.'
                   'OpenAlprCloudEntity.should_poll',
                   new_callable=PropertyMock(return_value=False)):
            setup_component(self.hass, ip.DOMAIN, config)

        state = self.hass.states.get('camera.demo_camera')
        self.url = "{0}{1}".format(
            self.hass.config.api.base_url,
            state.attributes.get(ATTR_ENTITY_PICTURE))

        self.alpr_events = []

        @callback
        def mock_alpr_event(event):
            """Mock event."""
            self.alpr_events.append(event)

        self.hass.bus.listen('image_processing.found_plate', mock_alpr_event)

        self.params = {
            'secret_key': "sk_abcxyz123456",
            'tasks': "plate",
            'return_image': 0,
            'country': 'eu',
            'image_bytes': "aW1hZ2U="
        }

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_openalpr_process_image(self, aioclient_mock):
        """Setup and scan a picture and test plates from event."""
        aioclient_mock.get(self.url, content=b'image')
        aioclient_mock.post(
            OPENALPR_API_URL, params=self.params,
            text=load_fixture('alpr_cloud.json'), status=200
        )

        ip.scan(self.hass, entity_id='image_processing.test_local')
        self.hass.block_till_done()

        state = self.hass.states.get('image_processing.test_local')

        assert len(aioclient_mock.mock_calls) == 2
        assert len(self.alpr_events) == 5
        assert state.attributes.get('vehicles') == 1
        assert state.state == 'H786P0J'

        event_data = [event.data for event in self.alpr_events if
                      event.data.get('plate') == 'H786P0J']
        assert len(event_data) == 1
        assert event_data[0]['plate'] == 'H786P0J'
        assert event_data[0]['confidence'] == float(90.436699)
        assert event_data[0]['entity_id'] == \
            'image_processing.test_local'

    def test_openalpr_process_image_api_error(self, aioclient_mock):
        """Setup and scan a picture and test api error."""
        aioclient_mock.get(self.url, content=b'image')
        aioclient_mock.post(
            OPENALPR_API_URL, params=self.params,
            text="{'error': 'error message'}", status=400
        )

        ip.scan(self.hass, entity_id='image_processing.test_local')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert len(self.alpr_events) == 0

    def test_openalpr_process_image_api_timeout(self, aioclient_mock):
        """Setup and scan a picture and test api error."""
        aioclient_mock.get(self.url, content=b'image')
        aioclient_mock.post(
            OPENALPR_API_URL, params=self.params,
            exc=asyncio.TimeoutError()
        )

        ip.scan(self.hass, entity_id='image_processing.test_local')
        self.hass.block_till_done()

        assert len(aioclient_mock.mock_calls) == 2
        assert len(self.alpr_events) == 0
