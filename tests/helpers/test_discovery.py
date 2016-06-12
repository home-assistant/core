"""Test discovery helpers."""

from unittest.mock import patch

from homeassistant.helpers import discovery

from tests.common import get_test_home_assistant


class TestHelpersDiscovery:
    """Tests for discovery helper methods."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.bootstrap.setup_component')
    def test_listen(self, mock_setup_component):
        """Test discovery listen/discover combo."""
        calls_single = []
        calls_multi = []

        def callback_single(service, info):
            """Service discovered callback."""
            calls_single.append((service, info))

        def callback_multi(service, info):
            """Service discovered callback."""
            calls_multi.append((service, info))

        discovery.listen(self.hass, 'test service', callback_single)
        discovery.listen(self.hass, ['test service', 'another service'],
                         callback_multi)

        discovery.discover(self.hass, 'test service', 'discovery info',
                           'test_component')
        self.hass.pool.block_till_done()

        discovery.discover(self.hass, 'another service', 'discovery info',
                           'test_component')
        self.hass.pool.block_till_done()

        assert mock_setup_component.called
        assert mock_setup_component.call_args[0] == \
            (self.hass, 'test_component', None)
        assert len(calls_single) == 1
        assert calls_single[0] == ('test service', 'discovery info')

        assert len(calls_single) == 1
        assert len(calls_multi) == 2
        assert ['test service', 'another service'] == [info[0] for info
                                                       in calls_multi]

    @patch('homeassistant.bootstrap.setup_component')
    def test_platform(self, mock_setup_component):
        """Test discover platform method."""
        calls = []

        def platform_callback(platform, info):
            """Platform callback method."""
            calls.append((platform, info))

        discovery.listen_platform(self.hass, 'test_component',
                                  platform_callback)

        discovery.load_platform(self.hass, 'test_component', 'test_platform',
                                'discovery info')
        assert mock_setup_component.called
        assert mock_setup_component.call_args[0] == \
            (self.hass, 'test_component', None)
        self.hass.pool.block_till_done()

        discovery.load_platform(self.hass, 'test_component_2', 'test_platform',
                                'discovery info')
        self.hass.pool.block_till_done()

        assert len(calls) == 1
        assert calls[0] == ('test_platform', 'discovery info')

        self.hass.bus.fire(discovery.EVENT_PLATFORM_DISCOVERED, {
            discovery.ATTR_SERVICE:
            discovery.EVENT_LOAD_PLATFORM.format('test_component')
        })
        self.hass.pool.block_till_done()

        assert len(calls) == 1
