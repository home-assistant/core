"""The tests for the openalpr local platform."""
import asyncio
from unittest.mock import patch, PropertyMock, MagicMock

from homeassistant.core import callback
from homeassistant.const import ATTR_ENTITY_PICTURE
from homeassistant.setup import setup_component
import homeassistant.components.image_processing as ip

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture)


@asyncio.coroutine
def mock_async_subprocess():
    """Get a Popen mock back."""
    async_popen = MagicMock()

    @asyncio.coroutine
    def communicate(input=None):
        """Communicate mock."""
        fixture = bytes(load_fixture('alpr_stdout.txt'), 'utf-8')
        return (fixture, None)

    async_popen.communicate = communicate
    return async_popen


class TestOpenAlprLocalSetup:
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
                'platform': 'openalpr_local',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
                'region': 'eu',
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
                'platform': 'openalpr_local',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
                'region': 'eu',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(1, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)

        assert self.hass.states.get('image_processing.test_local')

    def test_setup_platform_without_region(self):
        """Setup platform with one entity without region."""
        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_local',
                'source': {
                    'entity_id': 'camera.demo_camera'
                },
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with assert_setup_component(0, ip.DOMAIN):
            setup_component(self.hass, ip.DOMAIN, config)


class TestOpenAlprLocal:
    """Test class for image processing."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

        config = {
            ip.DOMAIN: {
                'platform': 'openalpr_local',
                'source': {
                    'entity_id': 'camera.demo_camera',
                    'name': 'test local'
                },
                'region': 'eu',
            },
            'camera': {
                'platform': 'demo'
            },
        }

        with patch('homeassistant.components.image_processing.openalpr_local.'
                   'OpenAlprLocalEntity.should_poll',
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

    def teardown_method(self):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('asyncio.create_subprocess_exec',
           return_value=mock_async_subprocess())
    def test_openalpr_process_image(self, popen_mock, aioclient_mock):
        """Setup and scan a picture and test plates from event."""
        aioclient_mock.get(self.url, content=b'image')

        ip.scan(self.hass, entity_id='image_processing.test_local')
        self.hass.block_till_done()

        state = self.hass.states.get('image_processing.test_local')

        assert popen_mock.called
        assert len(self.alpr_events) == 5
        assert state.attributes.get('vehicles') == 1
        assert state.state == 'PE3R2X'

        event_data = [event.data for event in self.alpr_events if
                      event.data.get('plate') == 'PE3R2X']
        assert len(event_data) == 1
        assert event_data[0]['plate'] == 'PE3R2X'
        assert event_data[0]['confidence'] == float(98.9371)
        assert event_data[0]['entity_id'] == \
            'image_processing.test_local'
