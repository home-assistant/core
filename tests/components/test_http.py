"""The tests for the Home Assistant HTTP component."""
# pylint: disable=protected-access,too-many-public-methods
import logging

import eventlet
import requests

from homeassistant import bootstrap, const
import homeassistant.components.http as http

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
HA_HEADERS = {
    const.HTTP_HEADER_HA_AUTH: API_PASSWORD,
    const.HTTP_HEADER_CONTENT_TYPE: const.CONTENT_TYPE_JSON,
}

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
         http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, 'api')

    hass.start()

    eventlet.sleep(0.05)


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
        """Test ascces with wrong password."""
        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: 'wrongpassword'})

        assert req.status_code == 401

    def test_access_with_password_in_header(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.setLevel(logging.WARNING,
                        logger='requests.packages.urllib3.connectionpool')

        req = requests.get(
            _url(const.URL_API),
            headers={const.HTTP_HEADER_HA_AUTH: API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text()

        assert const.URL_API in logs
        assert API_PASSWORD not in logs

    def test_access_denied_with_wrong_password_in_url(self):
        """Test ascces with wrong password."""
        req = requests.get(_url(const.URL_API),
                           params={'api_password': 'wrongpassword'})

        assert req.status_code == 401

    def test_access_with_password_in_url(self, caplog):
        """Test access with password in URL."""
        # Hide logging from requests package that we use to test logging
        caplog.setLevel(logging.WARNING,
                        logger='requests.packages.urllib3.connectionpool')

        req = requests.get(_url(const.URL_API),
                           params={'api_password': API_PASSWORD})

        assert req.status_code == 200

        logs = caplog.text()

        assert const.URL_API in logs
        assert API_PASSWORD not in logs
