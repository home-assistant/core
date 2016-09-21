"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access,too-many-public-methods
import logging
import time

import requests

from homeassistant import bootstrap, const
import homeassistant.components.http as http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
HTTP_BASE = "127.0.0.1:{}".format(SERVER_PORT)
HTTP_BASE_URL = "http://{}".format(HTTP_BASE)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

CORS_ORIGINS = [HTTP_BASE_URL, HTTP_BASE]

hass = None


def _url(path=""):
    """Helper method to generate URLs."""
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """Initialize a Home Assistant server."""
    global hass

    hass = get_test_home_assistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SERVER_PORT,
                       http.CONF_CORS_ORIGINS: CORS_ORIGINS}})

    bootstrap.setup_component(hass, 'api')

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop the Home Assistant server."""
    hass.stop()


class TestHttp:
    """Test HTTP component."""

    def test_access_denied_without_password(self):
        """Test access without password."""
        req = requests.get(_url(const.URL_API))

        assert req.status_code == 401

    def test_access_denied_with_wrong_password_in_header(self):
        """Test access with wrong password."""
        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: 'wrongpassword'})

        assert req.status_code == 401

    def test_access_denied_with_ip_no_in_approved_ips(self, caplog):
        """Test access deniend with ip not in approved ip."""
        hass.wsgi.approved_ips = ['134.4.56.1']

        req = requests.get(_url(const.URL_API),
                           params={'api_password': ''})

        assert req.status_code == 401

    def test_access_with_password_in_header(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.set_level(logging.WARNING,
                         logger='requests.packages.urllib3.connectionpool')

        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text

        # assert const.URL_API in logs
        assert API_PASSWORD not in logs

    def test_access_denied_with_wrong_password_in_url(self):
        """Test access with wrong password."""
        req = requests.get(_url(const.URL_API),
                           params={'api_password': 'wrongpassword'})

        assert req.status_code == 401

    def test_access_with_password_in_url(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.set_level(logging.WARNING,
                         logger='requests.packages.urllib3.connectionpool')

        req = requests.get(_url(const.URL_API),
                           params={'api_password': API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text

        # assert const.URL_API in logs
        assert API_PASSWORD not in logs

    def test_access_with_ip_in_approved_ips(self, caplog):
        """Test access with approved ip."""
        hass.wsgi.approved_ips = ['127.0.0.1', '134.4.56.1']

        req = requests.get(_url(const.URL_API),
                           params={'api_password': ''})

        assert req.status_code == 200

    def test_cors_allowed_with_password_in_url(self):
        """Test cross origin resource sharing with password in url."""
        req = requests.get(_url(const.URL_API),
                           params={'api_password': API_PASSWORD},
                           headers={const.HTTP_HEADER_ORIGIN: HTTP_BASE_URL})

        allow_origin = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS
        all_allow_headers = ", ".join(const.ALLOWED_CORS_HEADERS)

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL
        assert req.headers.get(allow_headers) == all_allow_headers

    def test_cors_allowed_with_password_in_header(self):
        """Test cross origin resource sharing with password in header."""
        headers = {
            const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
            const.HTTP_HEADER_ORIGIN: HTTP_BASE_URL
        }
        req = requests.get(_url(const.URL_API),
                           headers=headers)

        allow_origin = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS
        all_allow_headers = ", ".join(const.ALLOWED_CORS_HEADERS)

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL
        assert req.headers.get(allow_headers) == all_allow_headers

    def test_cors_denied_without_origin_header(self):
        """Test cross origin resource sharing with password in header."""
        headers = {
            const.HTTP_HEADER_HA_AUTH: API_PASSWORD
        }
        req = requests.get(_url(const.URL_API),
                           headers=headers)

        allow_origin = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS

        assert req.status_code == 200
        assert allow_origin not in req.headers
        assert allow_headers not in req.headers

    def test_cors_preflight_allowed(self):
        """Test cross origin resource sharing preflight (OPTIONS) request."""
        headers = {
            const.HTTP_HEADER_ORIGIN: HTTP_BASE_URL,
            'Access-Control-Request-Method': 'GET',
            'Access-Control-Request-Headers': 'x-ha-access'
        }
        req = requests.options(_url(const.URL_API),
                               headers=headers)

        allow_origin = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_ORIGIN
        allow_headers = const.HTTP_HEADER_ACCESS_CONTROL_ALLOW_HEADERS
        all_allow_headers = ", ".join(const.ALLOWED_CORS_HEADERS)

        assert req.status_code == 200
        assert req.headers.get(allow_origin) == HTTP_BASE_URL
        assert req.headers.get(allow_headers) == all_allow_headers
