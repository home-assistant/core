"""The tests for the UPC ConnextBox device tracker platform."""
import asyncio

from asynctest import patch
import pytest

from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.upc_connect.device_tracker as platform
from homeassistant.const import CONF_HOST, CONF_PLATFORM
from homeassistant.setup import async_setup_component

from tests.common import assert_setup_component, load_fixture, mock_component

HOST = "127.0.0.1"


async def async_scan_devices_mock(scanner):
    """Mock async_scan_devices."""
    return []


@pytest.fixture(autouse=True)
def setup_comp_deps(hass, mock_device_tracker_conf):
    """Set up component dependencies."""
    mock_component(hass, 'zone')
    mock_component(hass, 'group')
    yield


async def test_setup_platform_timeout_loginpage(hass, caplog, aioclient_mock):
    """Set up a platform with timeout on loginpage."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        exc=asyncio.TimeoutError()
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful',
    )

    assert await async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    assert 'Error setting up platform' in caplog.text


async def test_setup_platform_timeout_webservice(hass, caplog, aioclient_mock):
    """Set up a platform with api timeout."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'},
        content=b'successful',
        exc=asyncio.TimeoutError()
    )

    assert await async_setup_component(
        hass, DOMAIN, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    assert 'Error setting up platform' in caplog.text


@patch('homeassistant.components.upc_connect.device_tracker.'
       'UPCDeviceScanner.async_scan_devices',
       return_value=async_scan_devices_mock)
async def test_setup_platform(scan_mock, hass, aioclient_mock):
    """Set up a platform."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful'
    )

    with assert_setup_component(1, DOMAIN):
        assert await async_setup_component(
            hass, DOMAIN, {DOMAIN: {
                CONF_PLATFORM: 'upc_connect',
                CONF_HOST: HOST
            }})

    assert len(aioclient_mock.mock_calls) == 1


async def test_scan_devices(hass, aioclient_mock):
    """Set up a upc platform and scan device."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful',
        cookies={'sessionToken': '654321'}
    )

    scanner = await platform.async_get_scanner(
        hass, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        text=load_fixture('upc_connect.xml'),
        cookies={'sessionToken': '1235678'}
    )

    mac_list = await scanner.async_scan_devices()

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == 'token=654321&fun=123'
    assert mac_list == ['30:D3:2D:0:69:21', '5C:AA:FD:25:32:02',
                        '70:EE:50:27:A1:38']


async def test_scan_devices_without_session(hass, aioclient_mock):
    """Set up a upc platform and scan device with no token."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful',
        cookies={'sessionToken': '654321'}
    )

    scanner = await platform.async_get_scanner(
        hass, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        text=load_fixture('upc_connect.xml'),
        cookies={'sessionToken': '1235678'}
    )

    scanner.token = None
    mac_list = await scanner.async_scan_devices()

    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[1][2] == 'token=654321&fun=123'
    assert mac_list == ['30:D3:2D:0:69:21', '5C:AA:FD:25:32:02',
                        '70:EE:50:27:A1:38']


async def test_scan_devices_without_session_wrong_re(hass, aioclient_mock):
    """Set up a upc platform and scan device with no token and wrong."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful',
        cookies={'sessionToken': '654321'}
    )

    scanner = await platform.async_get_scanner(
        hass, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        status=400,
        cookies={'sessionToken': '1235678'}
    )

    scanner.token = None
    mac_list = await scanner.async_scan_devices()

    assert len(aioclient_mock.mock_calls) == 2
    assert aioclient_mock.mock_calls[1][2] == 'token=654321&fun=123'
    assert mac_list == []


async def test_scan_devices_parse_error(hass, aioclient_mock):
    """Set up a upc platform and scan device with parse error."""
    aioclient_mock.get(
        "http://{}/common_page/login.html".format(HOST),
        cookies={'sessionToken': '654321'}
    )
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        content=b'successful',
        cookies={'sessionToken': '654321'}
    )

    scanner = await platform.async_get_scanner(
        hass, {
            DOMAIN: {CONF_PLATFORM: 'upc_connect', CONF_HOST: HOST}})

    assert len(aioclient_mock.mock_calls) == 1

    aioclient_mock.clear_requests()
    aioclient_mock.post(
        "http://{}/xml/getter.xml".format(HOST),
        text="Blablebla blabalble",
        cookies={'sessionToken': '1235678'}
    )

    mac_list = await scanner.async_scan_devices()

    assert len(aioclient_mock.mock_calls) == 1
    assert aioclient_mock.mock_calls[0][2] == 'token=654321&fun=123'
    assert scanner.token is None
    assert mac_list == []
