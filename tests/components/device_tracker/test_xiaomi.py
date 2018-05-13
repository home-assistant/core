"""The tests for the Xiaomi router device tracker platform."""
import logging
import unittest
from unittest import mock
from unittest.mock import patch

import requests

from homeassistant.components.device_tracker import DOMAIN, xiaomi as xiaomi
from homeassistant.components.device_tracker.xiaomi import get_scanner
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PLATFORM)
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)

INVALID_USERNAME = 'bob'
TOKEN_TIMEOUT_USERNAME = 'tok'
URL_AUTHORIZE = 'http://192.168.0.1/cgi-bin/luci/api/xqsystem/login'
URL_LIST_END = 'api/misystem/devicelist'

FIRST_CALL = True


def mocked_requests(*args, **kwargs):
    """Mock requests.get invocations."""
    class MockResponse:
        """Class to represent a mocked response."""

        def __init__(self, json_data, status_code):
            """Initialize the mock response class."""
            self.json_data = json_data
            self.status_code = status_code

        def json(self):
            """Return the json of the response."""
            return self.json_data

        @property
        def content(self):
            """Return the content of the response."""
            return self.json()

        def raise_for_status(self):
            """Raise an HTTPError if status is not 200."""
            if self.status_code != 200:
                raise requests.HTTPError(self.status_code)

    data = kwargs.get('data')
    global FIRST_CALL

    if data and data.get('username', None) == INVALID_USERNAME:
        # deliver an invalid token
        return MockResponse({
            "code": "401",
            "msg": "Invalid token"
        }, 200)
    elif data and data.get('username', None) == TOKEN_TIMEOUT_USERNAME:
        # deliver an expired token
        return MockResponse({
            "url": "/cgi-bin/luci/;stok=ef5860/web/home",
            "token": "timedOut",
            "code": "0"
        }, 200)
    elif str(args[0]).startswith(URL_AUTHORIZE):
        # deliver an authorized token
        return MockResponse({
            "url": "/cgi-bin/luci/;stok=ef5860/web/home",
            "token": "ef5860",
            "code": "0"
        }, 200)
    elif str(args[0]).endswith("timedOut/" + URL_LIST_END) \
            and FIRST_CALL is True:
        FIRST_CALL = False
        # deliver an error when called with expired token
        return MockResponse({
            "code": "401",
            "msg": "Invalid token"
        }, 200)
    elif str(args[0]).endswith(URL_LIST_END):
        # deliver the device list
        return MockResponse({
            "mac": "1C:98:EC:0E:D5:A4",
            "list": [
                {
                    "mac": "23:83:BF:F6:38:A0",
                    "oname": "12255ff",
                    "isap": 0,
                    "parent": "",
                    "authority": {
                        "wan": 1,
                        "pridisk": 0,
                        "admin": 1,
                        "lan": 0
                    },
                    "push": 0,
                    "online": 1,
                    "name": "Device1",
                    "times": 0,
                    "ip": [
                        {
                            "downspeed": "0",
                            "online": "496957",
                            "active": 1,
                            "upspeed": "0",
                            "ip": "192.168.0.25"
                        }
                    ],
                    "statistics": {
                        "downspeed": "0",
                        "online": "496957",
                        "upspeed": "0"
                    },
                    "icon": "",
                    "type": 1
                },
                {
                    "mac": "1D:98:EC:5E:D5:A6",
                    "oname": "CdddFG58",
                    "isap": 0,
                    "parent": "",
                    "authority": {
                        "wan": 1,
                        "pridisk": 0,
                        "admin": 1,
                        "lan": 0
                    },
                    "push": 0,
                    "online": 1,
                    "name": "Device2",
                    "times": 0,
                    "ip": [
                        {
                            "downspeed": "0",
                            "online": "347325",
                            "active": 1,
                            "upspeed": "0",
                            "ip": "192.168.0.3"
                        }
                    ],
                    "statistics": {
                        "downspeed": "0",
                        "online": "347325",
                        "upspeed": "0"
                    },
                    "icon": "",
                    "type": 0
                },
            ],
            "code": 0
        }, 200)
    else:
        _LOGGER.debug('UNKNOWN ROUTE')


class TestXiaomiDeviceScanner(unittest.TestCase):
    """Xiaomi device scanner test class."""

    def setUp(self):
        """Initialize values for this testcase class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    @mock.patch(
        'homeassistant.components.device_tracker.xiaomi.XiaomiDeviceScanner',
        return_value=mock.MagicMock())
    def test_config(self, xiaomi_mock):
        """Testing minimal configuration."""
        config = {
            DOMAIN: xiaomi.PLATFORM_SCHEMA({
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: '192.168.0.1',
                CONF_PASSWORD: 'passwordTest'
            })
        }
        xiaomi.get_scanner(self.hass, config)
        self.assertEqual(xiaomi_mock.call_count, 1)
        self.assertEqual(xiaomi_mock.call_args, mock.call(config[DOMAIN]))
        call_arg = xiaomi_mock.call_args[0][0]
        self.assertEqual(call_arg['username'], 'admin')
        self.assertEqual(call_arg['password'], 'passwordTest')
        self.assertEqual(call_arg['host'], '192.168.0.1')
        self.assertEqual(call_arg['platform'], 'device_tracker')

    @mock.patch(
        'homeassistant.components.device_tracker.xiaomi.XiaomiDeviceScanner',
        return_value=mock.MagicMock())
    def test_config_full(self, xiaomi_mock):
        """Testing full configuration."""
        config = {
            DOMAIN: xiaomi.PLATFORM_SCHEMA({
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: '192.168.0.1',
                CONF_USERNAME: 'alternativeAdminName',
                CONF_PASSWORD: 'passwordTest'
            })
        }
        xiaomi.get_scanner(self.hass, config)
        self.assertEqual(xiaomi_mock.call_count, 1)
        self.assertEqual(xiaomi_mock.call_args, mock.call(config[DOMAIN]))
        call_arg = xiaomi_mock.call_args[0][0]
        self.assertEqual(call_arg['username'], 'alternativeAdminName')
        self.assertEqual(call_arg['password'], 'passwordTest')
        self.assertEqual(call_arg['host'], '192.168.0.1')
        self.assertEqual(call_arg['platform'], 'device_tracker')

    @patch('requests.get', side_effect=mocked_requests)
    @patch('requests.post', side_effect=mocked_requests)
    def test_invalid_credential(self, mock_get, mock_post):
        """Testing invalid credential handling."""
        config = {
            DOMAIN: xiaomi.PLATFORM_SCHEMA({
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: '192.168.0.1',
                CONF_USERNAME: INVALID_USERNAME,
                CONF_PASSWORD: 'passwordTest'
            })
        }
        self.assertIsNone(get_scanner(self.hass, config))

    @patch('requests.get', side_effect=mocked_requests)
    @patch('requests.post', side_effect=mocked_requests)
    def test_valid_credential(self, mock_get, mock_post):
        """Testing valid refresh."""
        config = {
            DOMAIN: xiaomi.PLATFORM_SCHEMA({
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: '192.168.0.1',
                CONF_USERNAME: 'admin',
                CONF_PASSWORD: 'passwordTest'
            })
        }
        scanner = get_scanner(self.hass, config)
        self.assertIsNotNone(scanner)
        self.assertEqual(2, len(scanner.scan_devices()))
        self.assertEqual("Device1",
                         scanner.get_device_name("23:83:BF:F6:38:A0"))
        self.assertEqual("Device2",
                         scanner.get_device_name("1D:98:EC:5E:D5:A6"))

    @patch('requests.get', side_effect=mocked_requests)
    @patch('requests.post', side_effect=mocked_requests)
    def test_token_timed_out(self, mock_get, mock_post):
        """Testing refresh with a timed out token.

        New token is requested and list is downloaded a second time.
        """
        config = {
            DOMAIN: xiaomi.PLATFORM_SCHEMA({
                CONF_PLATFORM: xiaomi.DOMAIN,
                CONF_HOST: '192.168.0.1',
                CONF_USERNAME: TOKEN_TIMEOUT_USERNAME,
                CONF_PASSWORD: 'passwordTest'
            })
        }
        scanner = get_scanner(self.hass, config)
        self.assertIsNotNone(scanner)
        self.assertEqual(2, len(scanner.scan_devices()))
        self.assertEqual("Device1",
                         scanner.get_device_name("23:83:BF:F6:38:A0"))
        self.assertEqual("Device2",
                         scanner.get_device_name("1D:98:EC:5E:D5:A6"))
