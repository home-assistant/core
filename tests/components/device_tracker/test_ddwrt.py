"""The tests for the DD-WRT device tracker platform."""
import os
import unittest
from unittest import mock
import logging
import re
import requests
import requests_mock

import pytest

from homeassistant import config
from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.const import (
    CONF_PLATFORM, CONF_HOST, CONF_PASSWORD, CONF_USERNAME)
from homeassistant.components.device_tracker import DOMAIN
from homeassistant.util import slugify

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture,
    mock_component)

from ...test_util.aiohttp import mock_aiohttp_client

TEST_HOST = '127.0.0.1'
_LOGGER = logging.getLogger(__name__)


@pytest.mark.skip
class TestDdwrt(unittest.TestCase):
    """Tests for the Ddwrt device tracker platform."""

    hass = None

    def run(self, result=None):
        """Mock out http calls to macvendor API for whole test suite."""
        with mock_aiohttp_client() as aioclient_mock:
            macvendor_re = re.compile('http://api.macvendors.com/.*')
            aioclient_mock.get(macvendor_re, text='')
            super().run(result)

    def setup_method(self, _):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'zone')

    def teardown_method(self, _):
        """Stop everything that was started."""
        self.hass.stop()
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

    @mock.patch('homeassistant.components.device_tracker.ddwrt._LOGGER.error')
    def test_login_failed(self, mock_error):
        """Create a Ddwrt scanner with wrong credentials."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                status_code=401)
            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})

                self.assertTrue(
                    'Failed to authenticate' in
                    str(mock_error.call_args_list[-1]))

    @mock.patch('homeassistant.components.device_tracker.ddwrt._LOGGER.error')
    def test_invalid_response(self, mock_error):
        """Test error handling when response has an error status."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                status_code=444)
            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})

                self.assertTrue(
                    'Invalid response from DD-WRT' in
                    str(mock_error.call_args_list[-1]))

    @mock.patch('homeassistant.components.device_tracker._LOGGER.error')
    @mock.patch('homeassistant.components.device_tracker.'
                'ddwrt.DdWrtDeviceScanner.get_ddwrt_data', return_value=None)
    def test_no_response(self, data_mock, error_mock):
        """Create a Ddwrt scanner with no response in init, should fail."""
        with assert_setup_component(1, DOMAIN):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'ddwrt',
                    CONF_HOST: TEST_HOST,
                    CONF_USERNAME: 'fake_user',
                    CONF_PASSWORD: '0'
                }})
            self.assertTrue(
                'Error setting up platform' in
                str(error_mock.call_args_list[-1]))

    @mock.patch('homeassistant.components.device_tracker.ddwrt.requests.get',
                side_effect=requests.exceptions.Timeout)
    @mock.patch('homeassistant.components.device_tracker.ddwrt._LOGGER.error')
    def test_get_timeout(self, mock_error, mock_request):
        """Test get Ddwrt data with request time out."""
        with assert_setup_component(1, DOMAIN):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'ddwrt',
                    CONF_HOST: TEST_HOST,
                    CONF_USERNAME: 'fake_user',
                    CONF_PASSWORD: '0'
                }})

            self.assertTrue(
                'Connection to the router timed out' in
                str(mock_error.call_args_list[-1]))

    def test_scan_devices(self):
        """Test creating device info (MAC, name) from response.

        The created known_devices.yaml device info is compared
        to the DD-WRT Lan Status request response fixture.
        This effectively checks the data parsing functions.
        """
        status_lan = load_fixture('Ddwrt_Status_Lan.txt')

        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Wireless.txt'))
            mock_request.register_uri(
                'GET', r'http://%s/Status_Lan.live.asp' % TEST_HOST,
                text=status_lan)

            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})
                self.hass.block_till_done()

            path = self.hass.config.path(device_tracker.YAML_DEVICES)
            devices = config.load_yaml_config_file(path)
            for device in devices:
                self.assertIn(devices[device]['mac'], status_lan)
                self.assertIn(slugify(devices[device]['name']), status_lan)

    def test_device_name_no_data(self):
        """Test creating device info (MAC only) when no response."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Wireless.txt'))
            mock_request.register_uri(
                'GET', r'http://%s/Status_Lan.live.asp' % TEST_HOST, text=None)

            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})
                self.hass.block_till_done()

            path = self.hass.config.path(device_tracker.YAML_DEVICES)
            devices = config.load_yaml_config_file(path)
            status_lan = load_fixture('Ddwrt_Status_Lan.txt')
            for device in devices:
                _LOGGER.error(devices[device])
                self.assertIn(devices[device]['mac'], status_lan)

    def test_device_name_no_dhcp(self):
        """Test creating device info (MAC) when missing dhcp response."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Wireless.txt'))
            mock_request.register_uri(
                'GET', r'http://%s/Status_Lan.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Lan.txt').
                replace('dhcp_leases', 'missing'))

            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})
                self.hass.block_till_done()

            path = self.hass.config.path(device_tracker.YAML_DEVICES)
            devices = config.load_yaml_config_file(path)
            status_lan = load_fixture('Ddwrt_Status_Lan.txt')
            for device in devices:
                _LOGGER.error(devices[device])
                self.assertIn(devices[device]['mac'], status_lan)

    def test_update_no_data(self):
        """Test error handling of no response when active devices checked."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                # First request has to work to setup connection
                [{'text': load_fixture('Ddwrt_Status_Wireless.txt')},
                 # Second request to get active devices fails
                 {'text': None}])
            mock_request.register_uri(
                'GET', r'http://%s/Status_Lan.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Lan.txt'))

            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})

    def test_update_wrong_data(self):
        """Test error handling of bad response when active devices checked."""
        with requests_mock.Mocker() as mock_request:
            mock_request.register_uri(
                'GET', r'http://%s/Status_Wireless.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Wireless.txt').
                replace('active_wireless', 'missing'))
            mock_request.register_uri(
                'GET', r'http://%s/Status_Lan.live.asp' % TEST_HOST,
                text=load_fixture('Ddwrt_Status_Lan.txt'))

            with assert_setup_component(1, DOMAIN):
                assert setup_component(
                    self.hass, DOMAIN, {DOMAIN: {
                        CONF_PLATFORM: 'ddwrt',
                        CONF_HOST: TEST_HOST,
                        CONF_USERNAME: 'fake_user',
                        CONF_PASSWORD: '0'
                    }})
