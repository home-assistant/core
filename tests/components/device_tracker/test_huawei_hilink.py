"""The tests for the Huawei HiLink router device tracker platform."""
import logging
import unittest
from unittest import mock

import requests_mock

from homeassistant.components.device_tracker import DOMAIN, huawei_hilink
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PLATFORM)
from tests.common import load_fixture

_LOGGER = logging.getLogger(__name__)

TEST_USERNAME = 'usernameTest'

TEST_CONFIG = {
    DOMAIN: huawei_hilink.PLATFORM_SCHEMA({
        CONF_PLATFORM: huawei_hilink.DOMAIN,
        CONF_HOST: '192.168.8.2',
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: 'passwordTest'
    })
}

HOST_LIST_URL = 'http://192.168.8.2/api/wlan/host-list'
LOGIN_URL = 'http://192.168.8.2/api/user/login'
AUTH_INFO_URL = 'http://192.168.8.2/api/webserver/SesTokInfo'

TEST_AUTH_INFO = huawei_hilink.AuthInfo(session_id='test_session_id',
                                        verification_token='test_token')

# Computed with 'usernameTest', 'passwordTest' and 'test_token'
PASSWORD_HASH = ("NTBhYzQxNmMzMGZjYWMwY2QyNTUwODg4OWIxMTc1MGE1OWJkZmJhYzNiYjA3"
                 "MGQ5ZDQyNjNlNGNhNzgyMGVmOA==")

AUTH_INFO_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<response>
<SesInfo>SessionID=test_session_id</SesInfo>
<TokInfo>test_token</TokInfo>
</response>
"""

OK_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<response>OK</response>
"""

ERROR_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<error>
<code>125002</code>
<message></message>
</error>
"""

HOST_LIST_FIXTURE = load_fixture('huawei_hilink_host_list.xml')


class TestHuaweiHiLinkDeviceScanner(unittest.TestCase):
    """Huawei HiLink device scanner test class."""

    @mock.patch('homeassistant.components.device_tracker.huawei_hilink.'
                'HuaweiHiLinkDeviceScanner')
    def test_config(self, scanner_mock):
        """Testing configuration."""
        config = {
            DOMAIN: huawei_hilink.PLATFORM_SCHEMA({
                CONF_PLATFORM: huawei_hilink.DOMAIN,
                CONF_HOST: '192.168.8.2',
                CONF_USERNAME: 'usernameTest',
                CONF_PASSWORD: 'passwordTest'
            })
        }

        huawei_hilink.get_scanner(hass=None, config=config)

        scanner_mock.assert_called_once_with(config[DOMAIN])

    @mock.patch('homeassistant.components.device_tracker.huawei_hilink.'
                'HuaweiHiLinkDeviceScanner')
    def test_default_config(self, scanner_mock):
        """Testing default configuration."""
        config = {
            DOMAIN: huawei_hilink.PLATFORM_SCHEMA({
                CONF_PLATFORM: huawei_hilink.DOMAIN
            })
        }

        huawei_hilink.get_scanner(hass=None, config=config)

        scanner_mock.assert_called_once_with(config[DOMAIN])
        config_arg = scanner_mock.call_args[0][0]
        self.assertEqual(config_arg[CONF_HOST],
                         huawei_hilink.DEFAULT_HOST)
        self.assertEqual(config_arg[CONF_USERNAME],
                         huawei_hilink.DEFAULT_USERNAME)
        self.assertEqual(config_arg[CONF_PASSWORD],
                         huawei_hilink.DEFAULT_PASSWORD)

    @requests_mock.Mocker()
    def test_scan_devices(self, mock_req):
        """Testing successful devices scanning."""
        mock_req.get(HOST_LIST_URL, text=HOST_LIST_FIXTURE)
        scanner = huawei_hilink.get_scanner(hass=None, config=TEST_CONFIG)

        devices = scanner.scan_devices()

        assert len(devices) == 3
        assert devices == ['0C:70:E0:2B:9A:F6', '6A:94:88:F6:C0:7B',
                           'C7:D7:D8:CB:E0:D0']

    @requests_mock.Mocker()
    def test_get_device_name(self, mock_req):
        """Testing getting device's name for MAC."""
        mock_req.get(HOST_LIST_URL, text=HOST_LIST_FIXTURE)
        scanner = huawei_hilink.get_scanner(hass=None, config=TEST_CONFIG)

        scanner.scan_devices()

        assert scanner.get_device_name('6A:94:88:F6:C0:7B') \
            == 'second-host-name'
        assert scanner.get_device_name('unknown') is None

    @requests_mock.Mocker()
    def test_login_when_host_list_failed(self, mock_req):
        """Testing login retry when retrieving host list fails."""
        mock_req.get(HOST_LIST_URL, [{'text': ERROR_RESPONSE},
                                     {'text': HOST_LIST_FIXTURE}])
        new_session_id = 'new_session_id'
        mock_req.post(LOGIN_URL,
                      text=OK_RESPONSE,
                      cookies={
                          huawei_hilink.SESSION_ID_COOKIE: new_session_id
                      })
        scanner = huawei_hilink.HuaweiHiLinkDeviceScanner(TEST_CONFIG[DOMAIN])
        scanner.auth_info = TEST_AUTH_INFO

        devices = scanner.scan_devices()

        assert len(devices) == 3
        assert len(mock_req.request_history) == 3
        login_req = mock_req.request_history[-2]
        assert login_req.url == LOGIN_URL
        assert TEST_USERNAME in login_req.text
        assert PASSWORD_HASH in login_req.text
        assert login_req.headers['Cookie'] == '{}={}'.format(
            huawei_hilink.SESSION_ID_COOKIE, TEST_AUTH_INFO.session_id)
        host_list_req = mock_req.last_request
        assert host_list_req.url == HOST_LIST_URL
        assert host_list_req.headers['Cookie'] == '{}={}'.format(
            huawei_hilink.SESSION_ID_COOKIE, new_session_id)

    @requests_mock.Mocker()
    def test_obtain_auth_info_when_login_failed(self, mock_req):
        """Testing obtaining fresh authorization info if login fails."""
        mock_req.get(HOST_LIST_URL, [{'text': ERROR_RESPONSE},
                                     {'text': HOST_LIST_FIXTURE}])
        mock_req.post(LOGIN_URL, [
            {'text': ERROR_RESPONSE},
            {'text': OK_RESPONSE, 'cookies': {
                huawei_hilink.SESSION_ID_COOKIE: TEST_AUTH_INFO.session_id
            }}
        ])
        mock_req.get(AUTH_INFO_URL, text=AUTH_INFO_RESPONSE)
        scanner = huawei_hilink.HuaweiHiLinkDeviceScanner(TEST_CONFIG[DOMAIN])

        devices = scanner.scan_devices()

        assert len(devices) == 3
        assert len(mock_req.request_history) == 5
        auth_info_req = mock_req.request_history[-3]
        assert auth_info_req.url == AUTH_INFO_URL
        login_req = mock_req.request_history[-2]
        assert login_req.url == LOGIN_URL
        assert login_req.headers['Cookie'] == '{}={}'.format(
            huawei_hilink.SESSION_ID_COOKIE, TEST_AUTH_INFO.session_id)
        assert login_req.headers[huawei_hilink.VERIFICATION_TOKEN_HEADER] \
            == TEST_AUTH_INFO.verification_token

    @requests_mock.Mocker()
    def test_exhaust_scan_devices_if_login_failed_again(self, mock_req):
        """Testing exhausted devices scanning if login fails two times."""
        mock_req.get(HOST_LIST_URL, text=ERROR_RESPONSE)
        mock_req.post(LOGIN_URL, [{'text': ERROR_RESPONSE}] * 2)
        mock_req.get(AUTH_INFO_URL, text=AUTH_INFO_RESPONSE)
        scanner = huawei_hilink.HuaweiHiLinkDeviceScanner(TEST_CONFIG[DOMAIN])

        devices = scanner.scan_devices()

        assert not devices
        assert len(mock_req.request_history) == 4
        assert mock_req.last_request.url == LOGIN_URL
