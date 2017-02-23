"""The tests for the discovery component."""
import unittest

from unittest import mock
from unittest.mock import patch

from homeassistant.bootstrap import setup_component
from homeassistant.components import discovery
from homeassistant.const import EVENT_HOMEASSISTANT_START

from tests.common import get_test_home_assistant

# One might consider to "mock" services, but it's easy enough to just use
# what is already available.
SERVICE = 'yamaha'
SERVICE_COMPONENT = 'media_player'

SERVICE_NO_PLATFORM = 'hass_ios'
SERVICE_NO_PLATFORM_COMPONENT = 'ios'
SERVICE_INFO = {'key': 'value'}  # Can be anything

UNKNOWN_SERVICE = 'this_service_will_never_be_supported'

BASE_CONFIG = {
    discovery.DOMAIN: {
        'ignore': []
    }
}

IGNORE_CONFIG = {
    discovery.DOMAIN: {
        'ignore': [SERVICE_NO_PLATFORM]
    }
}


@patch('netdisco.service.DiscoveryService')
@patch('homeassistant.components.discovery.load_platform')
@patch('homeassistant.components.discovery.discover')
class DiscoveryTest(unittest.TestCase):
    """Test the discovery component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.netdisco = mock.Mock()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def setup_discovery_component(self, discovery_service, config):
        """Setup the discovery component with mocked netdisco."""
        discovery_service.return_value = self.netdisco

        setup_component(self.hass, discovery.DOMAIN, config)

        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

    def discover_service(self, discovery_service, name):
        """Simulate that netdisco discovered a new service."""
        self.assertTrue(self.netdisco.add_listener.called)

        # Extract a refernce to the service listener
        args, _ = self.netdisco.add_listener.call_args
        listener = args[0]

        # Call the listener (just like netdisco does)
        listener(name, SERVICE_INFO)

    def test_netdisco_is_started(
            self, discover, load_platform, discovery_service):
        """Test that netdisco is started."""
        self.setup_discovery_component(discovery_service, BASE_CONFIG)
        self.assertTrue(self.netdisco.start.called)

    def test_unknown_service(
            self, discover, load_platform, discovery_service):
        """Test that unknown service is ignored."""
        self.setup_discovery_component(discovery_service, BASE_CONFIG)
        self.discover_service(discovery_service, UNKNOWN_SERVICE)

        self.assertFalse(load_platform.called)
        self.assertFalse(discover.called)

    def test_load_platform(
            self, discover, load_platform, discovery_service):
        """Test load a supported platform."""
        self.setup_discovery_component(discovery_service, BASE_CONFIG)
        self.discover_service(discovery_service, SERVICE)

        load_platform.assert_called_with(self.hass,
                                         SERVICE_COMPONENT,
                                         SERVICE,
                                         SERVICE_INFO,
                                         BASE_CONFIG)

    def test_discover_platform(
            self, discover, load_platform, discovery_service):
        """Test discover a supported platform."""
        self.setup_discovery_component(discovery_service, BASE_CONFIG)
        self.discover_service(discovery_service, SERVICE_NO_PLATFORM)

        discover.assert_called_with(self.hass,
                                    SERVICE_NO_PLATFORM,
                                    SERVICE_INFO,
                                    SERVICE_NO_PLATFORM_COMPONENT,
                                    BASE_CONFIG)

    def test_ignore_platforms(
            self, discover, load_platform, discovery_service):
        """Test that ignored platforms are not setup."""
        self.setup_discovery_component(discovery_service, IGNORE_CONFIG)

        self.discover_service(discovery_service, SERVICE_NO_PLATFORM)
        self.assertFalse(discover.called)

        self.discover_service(discovery_service, SERVICE)
        self.assertTrue(load_platform.called)
