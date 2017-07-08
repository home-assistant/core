"""Tests for Wake On LAN component."""
import unittest
from unittest.mock import patch

from homeassistant.setup import setup_component
from homeassistant.components import wake_on_lan

from tests.common import get_test_home_assistant


class TestWakeOnLAN(unittest.TestCase):
    """Test the Wake On LAN component."""

    def setUp(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_component(self):
        """Test the set up of new component."""
        self.assertTrue(setup_component(self.hass, wake_on_lan.DOMAIN, {
            wake_on_lan.DOMAIN: {}
        }))

        self.assertTrue(self.hass.services.has_service(
            'wake_on_lan', 'send_magic_packet'))

    @patch('homeassistant.core._LOGGER.error')
    def test_service_call_bad_params(self, mock_log):
        """Test of service parameters of send magic packet."""
        setup_component(self.hass, wake_on_lan.DOMAIN,
                        {wake_on_lan.DOMAIN: {}})

        self.hass.services.call('wake_on_lan', 'send_magic_packet',
                                blocking=True)
        self.assertEqual(1, mock_log.call_count)

        self.hass.services.call('wake_on_lan', 'send_magic_packet',
                                {}, blocking=True)
        self.assertEqual(2, mock_log.call_count)

        # Send a real magic packet to a non existent MAC address
        self.hass.services.call('wake_on_lan', 'send_magic_packet',
                                {"mac": "aa:bb:cc:dd:ee:ff"}, blocking=True)
        self.assertEqual(2, mock_log.call_count)

    @patch('wakeonlan.wol.send_magic_packet')
    def test_send_magic_packet(self, mock_log):
        """Test of send magic packet service call."""
        setup_component(self.hass, wake_on_lan.DOMAIN,
                        {wake_on_lan.DOMAIN: {}})

        self.hass.services.call(
            'wake_on_lan', 'send_magic_packet',
            {"mac": "aa:bb:cc:dd:ee:ff"}, blocking=True)
        self.assertEqual(1, mock_log.call_count)

        self.hass.services.call(
            'wake_on_lan', 'send_magic_packet',
            {"mac": "aa:bb:cc:dd:ee:ff",
             "broadcast_address": "192.168.255.255"},
            blocking=True)
        self.assertEqual(2, mock_log.call_count)

        self.hass.services.call(
            'wake_on_lan', 'send_magic_packet',
            {"broadcast_address": "192.168.255.255"},
            blocking=True)
        self.assertEqual(2, mock_log.call_count)
