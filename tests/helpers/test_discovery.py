"""Test discovery helpers."""
from collections import OrderedDict
from unittest.mock import patch

from homeassistant import loader, bootstrap
from homeassistant.core import callback
from homeassistant.helpers import discovery
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import (
    get_test_home_assistant, MockModule, MockPlatform, mock_coro)


class TestHelpersDiscovery:
    """Tests for discovery helper methods."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def teardown_method(self, method):
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.bootstrap.async_setup_component')
    def test_listen(self, mock_setup_component):
        """Test discovery listen/discover combo."""
        calls_single = []
        calls_multi = []

        @callback
        def callback_single(service, info):
            """Service discovered callback."""
            calls_single.append((service, info))

        @callback
        def callback_multi(service, info):
            """Service discovered callback."""
            calls_multi.append((service, info))

        discovery.listen(self.hass, 'test service', callback_single)
        discovery.listen(self.hass, ['test service', 'another service'],
                         callback_multi)

        discovery.discover(self.hass, 'test service', 'discovery info',
                           'test_component')
        self.hass.block_till_done()

        assert mock_setup_component.called
        assert mock_setup_component.call_args[0] == \
            (self.hass, 'test_component', None)
        assert len(calls_single) == 1
        assert calls_single[0] == ('test service', 'discovery info')

        discovery.discover(self.hass, 'another service', 'discovery info',
                           'test_component')
        self.hass.block_till_done()

        assert len(calls_single) == 1
        assert len(calls_multi) == 2
        assert ['test service', 'another service'] == [info[0] for info
                                                       in calls_multi]

    @patch('homeassistant.bootstrap.async_setup_component',
           return_value=mock_coro(True)())
    def test_platform(self, mock_setup_component):
        """Test discover platform method."""
        calls = []

        @callback
        def platform_callback(platform, info):
            """Platform callback method."""
            calls.append((platform, info))

        discovery.listen_platform(self.hass, 'test_component',
                                  platform_callback)

        discovery.load_platform(self.hass, 'test_component', 'test_platform',
                                'discovery info')
        self.hass.block_till_done()
        assert mock_setup_component.called
        assert mock_setup_component.call_args[0] == \
            (self.hass, 'test_component', None)
        self.hass.block_till_done()

        discovery.load_platform(self.hass, 'test_component_2', 'test_platform',
                                'discovery info')
        self.hass.block_till_done()

        assert len(calls) == 1
        assert calls[0] == ('test_platform', 'discovery info')

        self.hass.bus.fire(discovery.EVENT_PLATFORM_DISCOVERED, {
            discovery.ATTR_SERVICE:
            discovery.EVENT_LOAD_PLATFORM.format('test_component')
        })
        self.hass.block_till_done()

        assert len(calls) == 1

    def test_circular_import(self):
        """Test we don't break doing circular import.

        This test will have test_component discover the switch.test_circular
        component while setting up.

        The supplied config will load test_component and will load
        switch.test_circular.

        That means that after startup, we will have test_component and switch
        setup. The test_circular platform has been loaded twice.
        """
        component_calls = []
        platform_calls = []

        def component_setup(hass, config):
            """Setup mock component."""
            discovery.load_platform(hass, 'switch', 'test_circular', 'disc',
                                    config)
            component_calls.append(1)
            return True

        def setup_platform(hass, config, add_devices_callback,
                           discovery_info=None):
            """Setup mock platform."""
            platform_calls.append('disc' if discovery_info else 'component')

        loader.set_component(
            'test_component',
            MockModule('test_component', setup=component_setup))

        loader.set_component(
            'switch.test_circular',
            MockPlatform(setup_platform,
                         dependencies=['test_component']))

        bootstrap.setup_component(self.hass, 'test_component', {
            'test_component': None,
            'switch': [{
                'platform': 'test_circular',
            }],
        })

        # We wait for the setup_lock to finish
        run_coroutine_threadsafe(
            self.hass.data['setup_lock'].acquire(), self.hass.loop).result()

        self.hass.block_till_done()

        # test_component will only be setup once
        assert len(component_calls) == 1
        # The platform will be setup once via the config in `setup_component`
        # and once via the discovery inside test_component.
        assert len(platform_calls) == 2
        assert 'test_component' in self.hass.config.components
        assert 'switch' in self.hass.config.components

    def test_1st_discovers_2nd_component(self):
        """Test that we don't break if one component discovers the other.

        If the first component fires a discovery event to setup the
        second component while the second component is about to be setup,
        it should not setup the second component twice.
        """
        component_calls = []

        def component1_setup(hass, config):
            """Setup mock component."""
            discovery.discover(hass, 'test_component2',
                               component='test_component2')
            return True

        def component2_setup(hass, config):
            """Setup mock component."""
            component_calls.append(1)
            return True

        loader.set_component(
            'test_component1',
            MockModule('test_component1', setup=component1_setup))

        loader.set_component(
            'test_component2',
            MockModule('test_component2', setup=component2_setup))

        config = OrderedDict()
        config['test_component1'] = {}
        config['test_component2'] = {}

        self.hass.loop.run_until_complete = \
            lambda _: self.hass.block_till_done()

        bootstrap.from_config_dict(config, self.hass)

        self.hass.block_till_done()

        # test_component will only be setup once
        assert len(component_calls) == 1
