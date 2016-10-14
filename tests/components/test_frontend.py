"""The tests for Home Assistant frontend."""
# pylint: disable=protected-access,too-many-public-methods
import re
import time
import unittest

import requests

import homeassistant.bootstrap as bootstrap
from homeassistant.components import frontend, http
from homeassistant.const import HTTP_HEADER_HA_AUTH

from tests.common import get_test_instance_port, get_test_home_assistant

API_PASSWORD = "test1234"
SERVER_PORT = get_test_instance_port()
HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)
HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

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

    bootstrap.setup_component(hass, 'frontend')

    hass.start()
    time.sleep(0.05)


def tearDownModule():   # pylint: disable=invalid-name
    """Stop everything that was started."""
    hass.stop()
    frontend.PANELS = {}


class TestFrontend(unittest.TestCase):
    """Test the frontend."""

    def tearDown(self):
        """Stop everything that was started."""
        hass.block_till_done()

    def test_frontend_and_static(self):
        """Test if we can get the frontend."""
        req = requests.get(_url(""))

        self.assertEqual(200, req.status_code)

        # Test we can retrieve frontend.js
        frontendjs = re.search(
            r'(?P<app>\/static\/frontend-[A-Za-z0-9]{32}.html)',
            req.text)

        self.assertIsNotNone(frontendjs)

        req = requests.head(_url(frontendjs.groups(0)[0]))

        self.assertEqual(200, req.status_code)

    def test_404(self):
        """Test for HTTP 404 error."""
        self.assertEqual(404, requests.get(_url("/not-existing")).status_code)

    def test_we_cannot_POST_to_root(self):
        """Test that POST is not allow to root."""
        self.assertEqual(405, requests.post(_url("")).status_code)
