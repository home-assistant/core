"""The tests for Efergy sensor platform."""
import unittest

import requests_mock

from homeassistant.setup import setup_component
import homeassistant.components.device_tracker as device_tracker
from homeassistant.const import (
    CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_SSL)

from tests.common import load_fixture, get_test_home_assistant

token = 'bf13be9ca4cea446c49410963492282a'

LUCI_CONFIG = {
    'platform': 'luci',
    CONF_HOST: "127.0.0.1",
    CONF_USERNAME: 'blahuser',
    CONF_PASSWORD: "blahpass",
    CONF_SSL: False
}


def mock_responses_version_pre_18(mock):
    """Mock responses for Luci RPC version pre-18."""
    base_url = 'http://{}'.format(LUCI_CONFIG[CONF_HOST])
    mock.post(
        '{}/cgi-bin/luci/rpc/auth'.format(base_url),
        text=load_fixture('luci_auth.json'))
    mock.post(
        '{}/cgi-bin/luci/rpc/sys?auth={}'.format(base_url, token),
        text=load_fixture('luci_arptable_legacy.json'))
    mock.post(
        '{}/cgi-bin/luci/rpc/uci?auth={}'.format(base_url, token),
        text=load_fixture('luci_dhcp.json'))


def mock_responses_version_v18(mock):
    """Mock responses for Luci RPC version v18."""
    base_url = 'http://{}'.format(LUCI_CONFIG[CONF_HOST])
    mock.post(
        '{}/cgi-bin/luci/rpc/auth'.format(base_url),
        text=load_fixture('luci_auth.json'))
    mock.post(
        '{}/cgi-bin/luci/rpc/sys?auth={}'.format(base_url, token),
        text=load_fixture('luci_arptable_v18.json'))
    mock.post(
        '{}/cgi-bin/luci/rpc/ip?auth={}'.format(base_url, token),
        text=load_fixture('luci_neighbors.json'))
    mock.post(
        '{}/cgi-bin/luci/rpc/uci?auth={}'.format(base_url, token),
        text=load_fixture('luci_dhcp.json'))


class TestLuciDeviceScanner(unittest.TestCase):
    """Tests the Luci device scanner platform."""

    DEVICES = []

    @requests_mock.Mocker()
    def add_devices(self, devices, mock):
        """Mock add devices."""
        mock_responses(mock)
        for device in devices:
            device.update()
            self.DEVICES.append(device)

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = LUCI_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def setup_luci_component(self):
        self.assertTrue(setup_component(self.hass,
            device_tracker.DOMAIN, {
            device_tracker.DOMAIN: LUCI_CONFIG
        }))
        self.hass.block_till_done()

    @requests_mock.Mocker()
    def test_pre_v18_success(self, mock):
        """Test for successfully setting up
        the Luci platform on pre-v18."""
        mock_responses_version_pre_18(mock)

        self.setup_luci_component()

        self.assertEqual('home', self.hass.states.get(
            'device_tracker.raspberrypi3').state)
        self.assertIsNone(self.hass.states.get(
            'device_tracker.b8e8995c6e12'))
        self.assertIsNone(self.hass.states.get(
            'device_tracker.b8e8995c6e10'))

        self.assertEqual('home', self.hass.states.get(
            'device_tracker.b8e8995c6e11').state)

    @requests_mock.Mocker()
    def test_v18_or_newer_success(self, mock):
        """Test for successfully setting up the Luci platform on v18.06+"""
        mock_responses_version_v18(mock)

        self.setup_luci_component()

        self.assertIsNone(self.hass.states.get(
            'device_tracker.188b400814b2'))
        self.assertEqual('home', self.hass.states.get(
            'device_tracker.mydevicename').state)

        self.assertEqual('home', self.hass.states.get(
            'device_tracker.b8e8995c6e15').state)
        self.assertEqual('home', self.hass.states.get(
            'device_tracker.b827eb117c22').state)
