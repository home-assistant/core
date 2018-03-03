"""Tests for the HomeKit component."""
import unittest
from unittest.mock import call, patch, ANY, Mock

from homeassistant import setup
from homeassistant.core import State
from homeassistant.components.homekit import HomeKit, CONFIG_SCHEMA
from homeassistant.components.homekit.accessories import HomeBridge
from homeassistant.components.homekit.const import (
    DOMAIN, HOMEKIT_FILE, CONF_AUTO_START, CONF_PIN_CODE,
    DEFAULT_PORT, SERVICE_HOMEKIT_START)
from homeassistant.const import (
    CONF_ENTITIES, CONF_PORT,
    EVENT_HOMEASSISTANT_START, EVENT_HOMEASSISTANT_STOP)

from tests.common import get_test_home_assistant

IP_ADDRESS = '127.0.0.1'
PATH_HOMEKIT = 'homeassistant.components.homekit'


def test_pin_deprecated(caplog):
    """Test pin deprecated method."""
    CONFIG_SCHEMA({DOMAIN: {
        CONF_PIN_CODE: '123-45-678', CONF_ENTITIES: {'demo.test': 2}}})
    assert len(caplog.records) == 1


class TestHomeKit(unittest.TestCase):
    """Test setup of HomeKit component and HomeKit class."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop down everything that was started."""
        self.hass.stop()

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_min(self, mock_homekit):
        """Test async_setup with min config options."""
        config = {DOMAIN: {CONF_PORT: 11111, CONF_ENTITIES: {'demo.test': 2}}}
        self.assertTrue(setup.setup_component(
            self.hass, DOMAIN, config))

        self.assertEqual(mock_homekit.mock_calls, [
            call(self.hass, 11111, {'demo.test': {'aid': 2}},
                 [EVENT_HOMEASSISTANT_START]),
            call().setup()])

        # Test auto start enabled
        mock_homekit.reset_mock()
        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(mock_homekit.mock_calls, [
            call().start_event_call(ANY)])

    @patch(PATH_HOMEKIT + '.HomeKit')
    def test_setup_auto_start_disabled(self, mock_homekit):
        """Test async_setup with auto start disabled and test service calls."""
        mock_homekit.return_value = homekit = Mock()

        config = {DOMAIN: {
            CONF_AUTO_START: False, CONF_ENTITIES: {'demo.test': 2}}}
        self.assertTrue(setup.setup_component(
            self.hass, DOMAIN, config))

        self.hass.bus.fire(EVENT_HOMEASSISTANT_START)
        self.hass.block_till_done()

        self.assertEqual(mock_homekit.mock_calls, [
            call(self.hass, DEFAULT_PORT, {'demo.test': {'aid': 2}},
                 [EVENT_HOMEASSISTANT_START]),
            call().setup()])

        # Test start call with driver stopped.
        homekit.reset_mock()
        homekit.configure_mock(**{'started': False})

        self.hass.components.homekit.start()
        self.assertEqual(homekit.mock_calls, [call.start()])

        # Test start call with driver started.
        homekit.reset_mock()
        homekit.configure_mock(**{'started': True})

        self.hass.services.call(DOMAIN, SERVICE_HOMEKIT_START)
        self.assertEqual(homekit.mock_calls, [])

    def test_homekit_setup(self):
        """Test setup of bridge and driver."""
        homekit = HomeKit(self.hass, DEFAULT_PORT, {'demo.test': {'aid': 2}},
                          [EVENT_HOMEASSISTANT_START])

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

    @patch(PATH_HOMEKIT + '.HomeKit.start')
    def test_homekit_start_event_call(self, mock_start):
        """Test if method calls start after all events have been logged."""
        homekit = HomeKit(None, None, None, ['event_1', 'event_2'])
        homekit.start_event_call('event_1')
        self.assertEqual(mock_start.mock_calls, [])
        homekit.start_event_call('event_2')
        self.assertEqual(mock_start.mock_calls, [call()])

    def test_homekit_add_accessory(self):
        """Add accessory if config exists and get_acc returns an accessory."""
        homekit = HomeKit(self.hass, None, {
            'demo.test': {'aid': 2}, 'demo.test_2': {'aid': 3}}, [])
        homekit.bridge = HomeBridge(self.hass)

        with patch(PATH_HOMEKIT + '.accessories.HomeBridge.add_accessory') \
            as mock_add_acc, \
                patch(PATH_HOMEKIT + '.get_accessory') as mock_get_acc:
            mock_get_acc.side_effect = [None, 'acc', None]
            homekit.add_bridge_accessory(State('light.demo', 'on'))
            self.assertFalse(mock_add_acc.called)
            homekit.add_bridge_accessory(State('demo.test', 'on'))
            self.assertFalse(mock_add_acc.called)
            homekit.add_bridge_accessory(State('demo.test_2', 'on'))
            self.assertEqual(mock_add_acc.mock_calls, [call('acc')])

    @patch(PATH_HOMEKIT + '.show_setup_message')
    @patch(PATH_HOMEKIT + '.HomeKit.add_bridge_accessory')
    def test_homekit_start(self, mock_add_bridge_acc, mock_show_setup_msg):
        """Test HomeKit start method."""
        homekit = HomeKit(self.hass, None, {'demo.test': {'aid': 2}}, [])
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
        homekit = HomeKit(None, None, None, [])
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
