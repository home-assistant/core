"""
tests.test_component_http
~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests Home Assistant HTTP component does what it should do.
"""
# pylint: disable=protected-access,too-many-public-methods
import re
import unittest

import requests

import homeassistant.core as ha
import homeassistant.bootstrap as bootstrap
import homeassistant.components.http as http
from homeassistant.const import HTTP_HEADER_HA_AUTH

API_PASSWORD = "test1234"

# Somehow the socket that holds the default port does not get released
# when we close down HA in a different test case. Until I have figured
# out what is going on, let's run this test on a different port.
SERVER_PORT = 8121

HTTP_BASE_URL = "http://127.0.0.1:{}".format(SERVER_PORT)

HA_HEADERS = {HTTP_HEADER_HA_AUTH: API_PASSWORD}

hass = None


def _url(path=""):
    """ Helper method to generate urls. """
    return HTTP_BASE_URL + path


def setUpModule():   # pylint: disable=invalid-name
    """ Initalizes a Home Assistant server. """
    global hass

    hass = ha.HomeAssistant()

    hass.bus.listen('test_event', lambda _: _)
    hass.states.set('test.test', 'a_state')

    bootstrap.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_API_PASSWORD: API_PASSWORD,
                       http.CONF_SERVER_PORT: SERVER_PORT}})

    bootstrap.setup_component(hass, 'frontend')

    hass.start()


def tearDownModule():   # pylint: disable=invalid-name
    """ Stops the Home Assistant server. """
    hass.stop()


class TestFrontend(unittest.TestCase):
    """ Test the frontend. """

    def test_frontend_and_static(self):
        """ Tests if we can get the frontend. """
        req = requests.get(_url(""))

        self.assertEqual(200, req.status_code)

        # Test we can retrieve frontend.js
        frontendjs = re.search(
            r'(?P<app>\/static\/frontend-[A-Za-z0-9]{32}.html)',
            req.text)

        self.assertIsNotNone(frontendjs)

        req = requests.head(_url(frontendjs.groups(0)[0]))

        self.assertEqual(200, req.status_code)

    def test_auto_filling_in_api_password(self):
        req = requests.get(
            _url("?{}={}".format(http.DATA_API_PASSWORD, API_PASSWORD)))

        self.assertEqual(200, req.status_code)

        auth_text = re.search(r"auth='{}'".format(API_PASSWORD), req.text)

        self.assertIsNotNone(auth_text)

    def test_404(self):
        self.assertEqual(404, requests.get(_url("/not-existing")).status_code)

    def test_we_cannot_POST_to_root(self):
        self.assertEqual(405, requests.post(_url("")).status_code)
