"""Tests for the HomeKit component."""
import unittest
from unittest.mock import call, patch, ANY, Mock

from homeassistant import setup
from homeassistant.core import State
from homeassistant.components.homekit import HomeKit, generate_aid
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    DOMAIN, HOMEKIT_FILE, CONF_AUTO_START,
    DEFAULT_PORT, SERVICE_HOMEKIT_START)
from homeassistant.helpers.entityfilter import generate_filter
from homeassistant.const import (
    CONF_PORT, EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

from tests.common import get_test_home_assistant

IP_ADDRESS = '127.0.0.1'
PATH_HOMEKIT = 'homeassistant.components.homekit'


class TestHomeKit(unittest.TestCase):
    """Test setup of HomeKit component and HomeKit class."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    def test_generate_aid(self):
        """Test generate aid method."""
        aid = generate_aid('demo.entity')
        self.assertIsInstance(aid, int)
        self.assertTrue(aid >= 2 and aid <= 18446744073709551615)

        with patch(PATH_HOMEKIT + '.adler32') as mock_adler32:
            mock_adler32.side_effect = [0, 1]
            self.assertIsNone(generate_aid('demo.entity'))

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_min(self, mock_homekit):
        """Test async_setup with min config options."""
        self.assertTrue(setup.setup_component(
            self.hass, DOMAIN, {DOMAIN: {}}))

        self.assertEqual(mock_homekit.mock_calls, [
            call(self.hass, DEFAULT_PORT, ANY, {}),
            call().setup()])

        # Test auto start enabled
        mock_homekit.reset_mock()
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(mock_homekit.mock_calls, [call().start(ANY)])

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_auto_start_disabled(self, mock_homekit):
        """Test async_setup with auto start disabled and test service calls."""
        mock_homekit.return_value = homekit = Mock()

        config = {DOMAIN: {CONF_AUTO_START: False, CONF_PORT: 11111}}
        self.assertTrue(setup.setup_component(
            self.hass, DOMAIN, config))

        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(mock_homekit.mock_calls, [
            call(self.hass, 11111, ANY, {}),
            call().setup()])

        # Test start call with driver stopped.
        homekit.reset_mock()
        homekit.configure_mock(**{'started': False})

        self.hass.services.call('homekit', 'start')
        self.assertEqual(homekit.mock_calls, [call.start()])

        # Test start call with driver started.
        homekit.reset_mock()
        homekit.configure_mock(**{'started': True})

        self.hass.services.call(DOMAIN, SERVICE_HOMEKIT_START)
        self.assertEqual(homekit.mock_calls, [])

    def test_homekit_setup(self):
        """Test setup of bridge and driver."""
        homekit = HomeKit(self.hass, DEFAULT_PORT, {}, {})

        with patch(PATH_HOMEKIT + '.accessories.HomeDriver') as mock_driver, \
                patch('homeassistant.util.get_local_ip') as mock_ip:
            mock_ip.return_value = IP_ADDRESS
            homekit.setup()

        path = self.hass.config.path(HOMEKIT_FILE)
        self.assertTrue(isinstance(homekit.bridge, HomeBridge))
        self.assertEqual(mock_driver.mock_calls, [
            call(homekit.bridge, DEFAULT_PORT, IP_ADDRESS, path)])

        # Test if stop listener is setup
        self.assertEqual(
            self.hass.bus.listeners.get(EVENT_HOMEASSISTANT_STOP), 1)

    def test_homekit_add_accessory(self):
        """Add accessory if config exists and get_acc returns an accessory."""
        homekit = HomeKit(self.hass, None, lambda entity_id: True, {})
        homekit.bridge = HomeBridge(self.hass)

        with patch(PATH_HOMEKIT + '.accessories.HomeBridge.add_accessory') \
            as mock_add_acc, \
                patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc:
            mock_get_acc.side_effect = [None, 'acc', None]
            homekit.add_bridge_accessory(State('light.demo', 'on'))
            self.assertEqual(mock_get_acc.call_args,
                             call(self.hass, ANY, 363398124, {}))
            self.assertFalse(mock_add_acc.called)
            homekit.add_bridge_accessory(State('demo.test', 'on'))
            self.assertEqual(mock_get_acc.call_args,
                             call(self.hass, ANY, 294192020, {}))
            self.assertTrue(mock_add_acc.called)
            homekit.add_bridge_accessory(State('demo.test_2', 'on'))
            self.assertEqual(mock_get_acc.call_args,
                             call(self.hass, ANY, 429982757, {}))
            self.assertEqual(mock_add_acc.mock_calls, [call('acc')])

    def test_homekit_entity_filter(self):
        """Test the entity filter."""
        entity_filter = generate_filter(['cover'], ['demo.test'], [], [])
        homekit = HomeKit(self.hass, None, entity_filter, {})

        with patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc:
            mock_get_acc.return_value = None

            homekit.add_bridge_accessory(State('cover.test', 'open'))
            self.assertTrue(mock_get_acc.called)
            mock_get_acc.reset_mock()

            homekit.add_bridge_accessory(State('demo.test', 'on'))
            self.assertTrue(mock_get_acc.called)
            mock_get_acc.reset_mock()

            homekit.add_bridge_accessory(State('light.demo', 'light'))
            self.assertFalse(mock_get_acc.called)

    @patch(PATH_HOMEKIT + '.show_setup_message')
    @patch(PATH_HOMEKIT + '.HomeKit.add_bridge_accessory')
    def test_homekit_start(self, mock_add_bridge_acc, mock_show_setup_msg):
        """Test HomeKit start method."""
        homekit = HomeKit(self.hass, None, {}, {'cover.demo': {}})
        homekit.bridge = HomeBridge(self.hass)
        homekit.driver = Mock()

        self.hass.states.set('light.demo', 'on')
        state = self.hass.states.all()[0]

        homekit.start()

        self.assertEqual(mock_add_bridge_acc.mock_calls, [call(state)])
        self.assertEqual(mock_show_setup_msg.mock_calls, [
            call(homekit.bridge, self.hass)])
        self.assertEqual(homekit.driver.mock_calls, [call.start()])
        self.assertTrue(homekit.started)

        # Test start() if already started
        homekit.driver.reset_mock()
        homekit.start()
        self.assertEqual(homekit.driver.mock_calls, [])

    def test_homekit_stop(self):
        """Test HomeKit stop method."""
        homekit = HomeKit(None, None, None, None)
        homekit.driver = Mock()

        # Test if started = False
        homekit.stop()
        self.assertFalse(homekit.driver.stop.called)

        # Test if driver not started
        homekit.started = True
        homekit.driver.configure_mock(**{'run_sentinel': None})
        homekit.stop()
        self.assertFalse(homekit.driver.stop.called)

        # Test if driver is started
        homekit.driver.configure_mock(**{'run_sentinel': 'sentinel'})
        homekit.stop()
        self.assertTrue(homekit.driver.stop.called)
