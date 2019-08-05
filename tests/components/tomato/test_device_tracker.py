"""The tests for the Tomato device tracker platform."""
from unittest import mock
import pytest
import requests
import requests_mock
import voluptuous as vol

from homeassistant.components.device_tracker import DOMAIN
import homeassistant.components.tomato.device_tracker as tomato
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PORT, CONF_SSL, CONF_PLATFORM,
                                 CONF_VERIFY_SSL)


def mock_session_response(*args, **kwargs):
    """Mock data generation for session response."""
    class MockSessionResponse:
        def __init__(self, text, status_code):
            self.text = text
            self.status_code = status_code

    # Username: foo
    # Password: bar
    if args[0].headers['Authorization'] != 'Basic Zm9vOmJhcg==':
        return MockSessionResponse(None, 401)
    if "gimmie_bad_data" in args[0].body:
        return MockSessionResponse('This shouldn\'t (wldev = be here.;', 200)
    if "gimmie_good_data" in args[0].body:
        return MockSessionResponse(
            "wldev = [ ['eth1','F4:F5:D8:AA:AA:AA',"
            "-42,5500,1000,7043,0],['eth1','58:EF:68:00:00:00',"
            "-42,5500,1000,7043,0]];\n"
            "dhcpd_lease = [ ['chromecast','172.10.10.5','F4:F5:D8:AA:AA:AA',"
            "'0 days, 16:17:08'],['wemo','172.10.10.6','58:EF:68:00:00:00',"
            "'0 days, 12:09:08']];", 200)

    return MockSessionResponse(None, 200)


@pytest.fixture
def mock_exception_logger():
    """Mock pyunifi."""
    with mock.patch('homeassistant.components.tomato.device_tracker'
                    '._LOGGER.exception') as mock_exception_logger:
        yield mock_exception_logger


@pytest.fixture
def mock_session_send():
    """Mock requests.Session().send."""
    with mock.patch('requests.Session.send') as mock_session_send:
        yield mock_session_send


def test_config_missing_optional_params(hass, mock_session_send):
    """Test the setup without optional parameters."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            tomato.CONF_HTTP_ID: '1234567890'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "http://tomato-router:80/update.cgi"
    assert result.req.headers == {
        'Content-Length': '32',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic Zm9vOnBhc3N3b3Jk'
    }
    assert "_http_id=1234567890" in result.req.body
    assert "exec=devlist" in result.req.body


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
def test_config_default_nonssl_port(hass, mock_session_send):
    """Test the setup without a default port set without ssl enabled."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            tomato.CONF_HTTP_ID: '1234567890'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "http://tomato-router:80/update.cgi"


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
def test_config_default_ssl_port(hass, mock_session_send):
    """Test the setup without a default port set with ssl enabled."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_SSL: True,
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            tomato.CONF_HTTP_ID: '1234567890'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "https://tomato-router:443/update.cgi"


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
def test_config_verify_ssl_but_no_ssl_enabled(hass, mock_session_send):
    """Test the setup with a string with ssl_verify but ssl not enabled."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: False,
            CONF_VERIFY_SSL: "/tmp/tomato.crt",
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'password',
            tomato.CONF_HTTP_ID: '1234567890'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "http://tomato-router:1234/update.cgi"
    assert result.req.headers == {
        'Content-Length': '32',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic Zm9vOnBhc3N3b3Jk'
    }
    assert "_http_id=1234567890" in result.req.body
    assert "exec=devlist" in result.req.body
    assert mock_session_send.call_count == 1
    assert mock_session_send.mock_calls[0] == \
        mock.call(result.req, timeout=3)


@mock.patch('os.access', return_value=True)
@mock.patch('os.path.isfile', mock.Mock(return_value=True))
def test_config_valid_verify_ssl_path(hass, mock_session_send):
    """Test the setup with a string for ssl_verify.

    Representing the absolute path to a CA certificate bundle.
    """
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "/tmp/tomato.crt",
            CONF_USERNAME: 'bar',
            CONF_PASSWORD: 'foo',
            tomato.CONF_HTTP_ID: '0987654321'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "https://tomato-router:1234/update.cgi"
    assert result.req.headers == {
        'Content-Length': '32',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic YmFyOmZvbw=='
    }
    assert "_http_id=0987654321" in result.req.body
    assert "exec=devlist" in result.req.body
    assert mock_session_send.call_count == 1
    assert mock_session_send.mock_calls[0] == \
        mock.call(result.req, timeout=3, verify="/tmp/tomato.crt")


def test_config_valid_verify_ssl_bool(hass, mock_session_send):
    """Test the setup with a bool for ssl_verify."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            CONF_USERNAME: 'bar',
            CONF_PASSWORD: 'foo',
            tomato.CONF_HTTP_ID: '0987654321'
        })
    }
    result = tomato.get_scanner(hass, config)
    assert result.req.url == "https://tomato-router:1234/update.cgi"
    assert result.req.headers == {
        'Content-Length': '32',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': 'Basic YmFyOmZvbw=='
    }
    assert "_http_id=0987654321" in result.req.body
    assert "exec=devlist" in result.req.body
    assert mock_session_send.call_count == 1
    assert mock_session_send.mock_calls[0] == \
        mock.call(result.req, timeout=3, verify=False)


def test_config_errors():
    """Test for configuration errors."""
    with pytest.raises(vol.Invalid):
        tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            # No Host,
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            CONF_USERNAME: 'bar',
            CONF_PASSWORD: 'foo',
            tomato.CONF_HTTP_ID: '0987654321'
        })
    with pytest.raises(vol.Invalid):
        tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: -123456789,  # Bad Port
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            CONF_USERNAME: 'bar',
            CONF_PASSWORD: 'foo',
            tomato.CONF_HTTP_ID: '0987654321'
        })
    with pytest.raises(vol.Invalid):
        tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            # No Username
            CONF_PASSWORD: 'foo',
            tomato.CONF_HTTP_ID: '0987654321'
        })
    with pytest.raises(vol.Invalid):
        tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            CONF_USERNAME: 'bar',
            # No Password
            tomato.CONF_HTTP_ID: '0987654321'
        })
    with pytest.raises(vol.Invalid):
        tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_PORT: 1234,
            CONF_SSL: True,
            CONF_VERIFY_SSL: "False",
            CONF_USERNAME: 'bar',
            CONF_PASSWORD: 'foo',
            # No HTTP_ID
        })


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_config_bad_credentials(hass, mock_exception_logger):
    """Test the setup with bad credentials."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'i_am',
            CONF_PASSWORD: 'an_imposter',
            tomato.CONF_HTTP_ID: '1234'
        })
    }

    tomato.get_scanner(hass, config)

    assert mock_exception_logger.call_count == 1
    assert mock_exception_logger.mock_calls[0] == \
        mock.call("Failed to authenticate, "
                  "please check your username and password")


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_bad_response(hass, mock_exception_logger):
    """Test the setup with bad response from router."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'bar',
            tomato.CONF_HTTP_ID: 'gimmie_bad_data'
        })
    }

    tomato.get_scanner(hass, config)

    assert mock_exception_logger.call_count == 1
    assert mock_exception_logger.mock_calls[0] == \
        mock.call("Failed to parse response from router")


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_scan_devices(hass, mock_exception_logger):
    """Test scanning for new devices."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'bar',
            tomato.CONF_HTTP_ID: 'gimmie_good_data'
        })
    }

    scanner = tomato.get_scanner(hass, config)
    assert scanner.scan_devices() == ['F4:F5:D8:AA:AA:AA', '58:EF:68:00:00:00']


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_bad_connection(hass, mock_exception_logger):
    """Test the router with a connection error."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'bar',
            tomato.CONF_HTTP_ID: 'gimmie_good_data'
        })
    }

    with requests_mock.Mocker() as adapter:
        adapter.register_uri('POST', 'http://tomato-router:80/update.cgi',
                             exc=requests.exceptions.ConnectionError),
        tomato.get_scanner(hass, config)
    assert mock_exception_logger.call_count == 1
    assert mock_exception_logger.mock_calls[0] == \
        mock.call("Failed to connect to the router "
                  "or invalid http_id supplied")


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_router_timeout(hass, mock_exception_logger):
    """Test the router with a timeout error."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'bar',
            tomato.CONF_HTTP_ID: 'gimmie_good_data'
        })
    }

    with requests_mock.Mocker() as adapter:
        adapter.register_uri('POST', 'http://tomato-router:80/update.cgi',
                             exc=requests.exceptions.Timeout),
        tomato.get_scanner(hass, config)
    assert mock_exception_logger.call_count == 1
    assert mock_exception_logger.mock_calls[0] == \
        mock.call("Connection to the router timed out")


@mock.patch('requests.Session.send', side_effect=mock_session_response)
def test_get_device_name(hass, mock_exception_logger):
    """Test getting device names."""
    config = {
        DOMAIN: tomato.PLATFORM_SCHEMA({
            CONF_PLATFORM: tomato.DOMAIN,
            CONF_HOST: 'tomato-router',
            CONF_USERNAME: 'foo',
            CONF_PASSWORD: 'bar',
            tomato.CONF_HTTP_ID: 'gimmie_good_data'
        })
    }

    scanner = tomato.get_scanner(hass, config)
    assert scanner.get_device_name('F4:F5:D8:AA:AA:AA') == 'chromecast'
    assert scanner.get_device_name('58:EF:68:00:00:00') == 'wemo'
    assert scanner.get_device_name('AA:BB:CC:00:00:00') is None
