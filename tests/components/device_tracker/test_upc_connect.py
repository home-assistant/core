"""The tests for the UPC ConnextBox device tracker platform."""
import asyncio
import os
from unittest.mock import patch
import logging

from homeassistant.setup import setup_component
from homeassistant.components import device_tracker
from homeassistant.const import (
    CONF_PLATFORM, CONF_HOST, CONF_PASSWORD)
from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.device_tracker.upc_connect as platform
from homeassistant.util.async import run_coroutine_threadsafe

from tests.common import (
    get_test_home_assistant, assert_setup_component, load_fixture,
    mock_component)

_LOGGER = logging.getLogger(__name__)


@asyncio.coroutine
def async_scan_devices_mock(scanner):
    """Mock async_scan_devices."""
    return []


class TestUPCConnect(object):
    """Tests for the Ddwrt device tracker platform."""

    def setup_method(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        mock_component(self.hass, 'zone')

        self.host = "127.0.0.1"

    def teardown_method(self):
        """Stop everything that was started."""
        try:
            os.remove(self.hass.config.path(device_tracker.YAML_DEVICES))
        except FileNotFoundError:
            pass

        self.hass.stop()

    @patch('homeassistant.components.device_tracker.upc_connect.'
           'UPCDeviceScanner.async_scan_devices',
           return_value=async_scan_devices_mock)
    def test_setup_platform(self, scan_mock, aioclient_mock):
        """Setup a platform."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful'
        )

        with assert_setup_component(1):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }})

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

    @patch('homeassistant.components.device_tracker._LOGGER.error')
    def test_setup_platform_error_webservice(self, mock_error, aioclient_mock):
        """Setup a platform with api error."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            status=404
        )

        with assert_setup_component(1):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }})

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        assert 'Error setting up platform' in \
            str(mock_error.call_args_list[-1])

    @patch('homeassistant.components.device_tracker._LOGGER.error')
    def test_setup_platform_timeout_webservice(self, mock_error,
                                               aioclient_mock):
        """Setup a platform with api timeout."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            exc=asyncio.TimeoutError()
        )

        with assert_setup_component(1):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }})

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        assert 'Error setting up platform' in \
            str(mock_error.call_args_list[-1])

    @patch('homeassistant.components.device_tracker._LOGGER.error')
    def test_setup_platform_timeout_loginpage(self, mock_error,
                                              aioclient_mock):
        """Setup a platform with timeout on loginpage."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            exc=asyncio.TimeoutError()
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
        )

        with assert_setup_component(1):
            assert setup_component(
                self.hass, DOMAIN, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }})

        assert len(aioclient_mock.mock_calls) == 1

        assert 'Error setting up platform' in \
            str(mock_error.call_args_list[-1])

    def test_scan_devices(self, aioclient_mock):
        """Setup a upc platform and scan device."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            cookies={'sessionToken': '654321'}
        )

        scanner = run_coroutine_threadsafe(platform.async_get_scanner(
            self.hass, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }}
            ), self.hass.loop).result()

        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        aioclient_mock.clear_requests()
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            text=load_fixture('upc_connect.xml'),
            cookies={'sessionToken': '1235678'}
        )

        mac_list = run_coroutine_threadsafe(
            scanner.async_scan_devices(), self.hass.loop).result()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['fun'] == 123
        assert scanner.token == '1235678'
        assert mac_list == ['30:D3:2D:0:69:21', '5C:AA:FD:25:32:02',
                            '70:EE:50:27:A1:38']

    def test_scan_devices_without_session(self, aioclient_mock):
        """Setup a upc platform and scan device with no token."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            cookies={'sessionToken': '654321'}
        )

        scanner = run_coroutine_threadsafe(platform.async_get_scanner(
            self.hass, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }}
            ), self.hass.loop).result()

        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        aioclient_mock.clear_requests()
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            text=load_fixture('upc_connect.xml'),
            cookies={'sessionToken': '1235678'}
        )

        scanner.token = None
        mac_list = run_coroutine_threadsafe(
            scanner.async_scan_devices(), self.hass.loop).result()

        assert len(aioclient_mock.mock_calls) == 3
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert mac_list == ['30:D3:2D:0:69:21', '5C:AA:FD:25:32:02',
                            '70:EE:50:27:A1:38']

    def test_scan_devices_without_session_wrong_re(self, aioclient_mock):
        """Setup a upc platform and scan device with no token and wrong."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            cookies={'sessionToken': '654321'}
        )

        scanner = run_coroutine_threadsafe(platform.async_get_scanner(
            self.hass, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }}
            ), self.hass.loop).result()

        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        aioclient_mock.clear_requests()
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            status=400,
            cookies={'sessionToken': '1235678'}
        )

        scanner.token = None
        mac_list = run_coroutine_threadsafe(
            scanner.async_scan_devices(), self.hass.loop).result()

        assert len(aioclient_mock.mock_calls) == 2
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert mac_list == []

    def test_scan_devices_parse_error(self, aioclient_mock):
        """Setup a upc platform and scan device with parse error."""
        aioclient_mock.get(
            "http://{}/common_page/login.html".format(self.host),
            cookies={'sessionToken': '654321'}
        )
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            content=b'successful',
            cookies={'sessionToken': '654321'}
        )

        scanner = run_coroutine_threadsafe(platform.async_get_scanner(
            self.hass, {DOMAIN: {
                    CONF_PLATFORM: 'upc_connect',
                    CONF_HOST: self.host,
                    CONF_PASSWORD: '123456'
                }}
            ), self.hass.loop).result()

        assert aioclient_mock.mock_calls[1][2]['Password'] == '123456'
        assert aioclient_mock.mock_calls[1][2]['fun'] == 15
        assert aioclient_mock.mock_calls[1][2]['token'] == '654321'

        aioclient_mock.clear_requests()
        aioclient_mock.post(
            "http://{}/xml/getter.xml".format(self.host),
            text="Blablebla blabalble",
            cookies={'sessionToken': '1235678'}
        )

        mac_list = run_coroutine_threadsafe(
            scanner.async_scan_devices(), self.hass.loop).result()

        assert len(aioclient_mock.mock_calls) == 1
        assert aioclient_mock.mock_calls[0][2]['fun'] == 123
        assert scanner.token is None
        assert mac_list == []
