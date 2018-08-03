"""The tests for the emulated Hue component."""
import json

import unittest
from unittest.mock import patch
import requests
from aiohttp.hdrs import CONTENT_TYPE

from homeassistant import setup, const, core
import homeassistant.components as core_components
from homeassistant.components import emulated_hue, http
from homeassistant.util.async_ import run_coroutine_threadsafe

from tests.common import get_test_instance_port, get_test_home_assistant

HTTP_SERVER_PORT = get_test_instance_port()
BRIDGE_SERVER_PORT = get_test_instance_port()

BRIDGE_URL_BASE = 'http://127.0.0.1:{}'.format(BRIDGE_SERVER_PORT) + '{}'
JSON_HEADERS = {CONTENT_TYPE: const.CONTENT_TYPE_JSON}


def setup_hass_instance(emulated_hue_config):
    """Set up the Home Assistant instance to test."""
    hass = get_test_home_assistant()

    # We need to do this to get access to homeassistant/turn_(on,off)
    run_coroutine_threadsafe(
        core_components.async_setup(hass, {core.DOMAIN: {}}), hass.loop
    ).result()

    setup.setup_component(
        hass, http.DOMAIN,
        {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}})

    setup.setup_component(hass, emulated_hue.DOMAIN, emulated_hue_config)

    return hass


def start_hass_instance(hass):
    """Start the Home Assistant instance to test."""
    hass.start()


class TestEmulatedHue(unittest.TestCase):
    """Test the emulated Hue component."""

    hass = None

    @classmethod
    def setUpClass(cls):
        """Setup the class."""
        cls.hass = hass = get_test_home_assistant()

        # We need to do this to get access to homeassistant/turn_(on,off)
        run_coroutine_threadsafe(
            core_components.async_setup(hass, {core.DOMAIN: {}}), hass.loop
        ).result()

        setup.setup_component(
            hass, http.DOMAIN,
            {http.DOMAIN: {http.CONF_SERVER_PORT: HTTP_SERVER_PORT}})

        with patch('homeassistant.components'
                   '.emulated_hue.UPNPResponderThread'):
            setup.setup_component(hass, emulated_hue.DOMAIN, {
                emulated_hue.DOMAIN: {
                    emulated_hue.CONF_LISTEN_PORT: BRIDGE_SERVER_PORT
                }})

        cls.hass.start()

    @classmethod
    def tearDownClass(cls):
        """Stop the class."""
        cls.hass.stop()

    def test_description_xml(self):
        """Test the description."""
        import xml.etree.ElementTree as ET

        result = requests.get(
            BRIDGE_URL_BASE.format('/description.xml'), timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('text/xml' in result.headers['content-type'])

        # Make sure the XML is parsable
        try:
            ET.fromstring(result.text)
        except:  # noqa: E722 pylint: disable=bare-except
            self.fail('description.xml is not valid XML!')

    def test_create_username(self):
        """Test the creation of an username."""
        request_json = {'devicetype': 'my_device'}

        result = requests.post(
            BRIDGE_URL_BASE.format('/api'), data=json.dumps(request_json),
            timeout=5)

        self.assertEqual(result.status_code, 200)
        self.assertTrue('application/json' in result.headers['content-type'])

        resp_json = result.json()
        success_json = resp_json[0]

        self.assertTrue('success' in success_json)
        self.assertTrue('username' in success_json['success'])

    def test_valid_username_request(self):
        """Test request with a valid username."""
        request_json = {'invalid_key': 'my_device'}

        result = requests.post(
            BRIDGE_URL_BASE.format('/api'), data=json.dumps(request_json),
            timeout=5)

        self.assertEqual(result.status_code, 400)
