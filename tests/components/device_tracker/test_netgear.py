import unittest
from unittest.mock import Mock, patch

from homeassistant.components.device_tracker import DOMAIN
from homeassistant.const import (
    CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_PORT)

from components.device_tracker import netgear

class NetgearTest(unittest.TestCase):
    """Test netgear platform."""

    @patch('pynetgear.Netgear', Mock())
    def test_get_scanner_valid_parameters(self):
        """Test get_scanner() with valid config."""
        config = {DOMAIN: {CONF_HOST: 'a', CONF_PASSWORD: 'b',
                           CONF_USERNAME: 'c', CONF_PORT: 80}}
        net = netgear.get_scanner(None, config)
        self.assertTrue(isinstance(net, netgear.NetgearDeviceScanner))

    def test_get_scanner_invalid_parameters(self):
        """Test get_scanner() with invalid config."""
        # host is missing
        config = {DOMAIN: {CONF_PASSWORD: 'b', CONF_USERNAME: 'c',
                           CONF_PORT: 80}}
        self.assertIsNone(netgear.get_scanner(None, config))

        # password is missing
        config = {DOMAIN: {CONF_HOST: 'a', CONF_USERNAME: 'c',
                           CONF_PORT: 80}}
        self.assertIsNone(netgear.get_scanner(None, config))

        # username is missing
        config = {DOMAIN: {CONF_HOST: 'a', CONF_PASSWORD: 'b',
                           CONF_PORT: 80}}
        self.assertIsNone(netgear.get_scanner(None, config))

        # port is missing
        config = {DOMAIN: {CONF_HOST: 'a', CONF_PASSWORD: 'b',
                           CONF_USERNAME: 'c'}}
        self.assertIsNone(netgear.get_scanner(None, config))

        # all parameters are missing
        config = {DOMAIN: {}}
        self.assertIsNone(netgear.get_scanner(None, config))