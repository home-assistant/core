"""The tests for the Ring component."""
from copy import deepcopy
import os
import unittest
import requests_mock

from homeassistant import setup
import homeassistant.components.ring as ring

from tests.common import (
    get_test_config_dir, get_test_home_assistant, load_fixture)

ATTRIBUTION = 'Data provided by Ring.com'

VALID_CONFIG = {
    "ring": {
        "username": "foo",
        "password": "bar",
    }
}


class TestRing(unittest.TestCase):
    """Tests the Ring component."""

    def cleanup(self):
        """Cleanup any data created from the tests."""
        if os.path.isfile(self.cache):
            os.remove(self.cache)

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.cache = get_test_config_dir(ring.DEFAULT_CACHEDB)
        self.config = VALID_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()
        self.cleanup()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test the setup."""
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        response = ring.setup(self.hass, self.config)
        self.assertTrue(response)

    @requests_mock.Mocker()
    def test_setup_component_no_login(self, mock):
        """Test the setup when no login is configured."""
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        conf = deepcopy(VALID_CONFIG)
        del conf['ring']['username']
        assert not setup.setup_component(self.hass, ring.DOMAIN, conf)

    @requests_mock.Mocker()
    def test_setup_component_no_pwd(self, mock):
        """Test the setup when no password is configured."""
        mock.post('https://api.ring.com/clients_api/session',
                  text=load_fixture('ring_session.json'))
        conf = deepcopy(VALID_CONFIG)
        del conf['ring']['password']
        assert not setup.setup_component(self.hass, ring.DOMAIN, conf)
