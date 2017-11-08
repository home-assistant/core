"""The tests for the Canary component."""
import copy
import unittest

import requests_mock

import homeassistant.components.canary as canary
from canary.api import URL_LOGIN_PAGE, COOKIE_SSESYRANAC, COOKIE_XSRF_TOKEN, \
    URL_LOGIN_API, URL_ME_API, URL_LOCATIONS_API, URL_READINGS_API, \
    URL_ENTRIES_API
from homeassistant import setup
from tests.common import (
    get_test_home_assistant, load_fixture)

VALID_CONFIG = {
    "canary": {
        "username": "foo@bar.org",
        "password": "bar",
    }
}

VALUE_XSRF_TOKEN = "&*GYG&*T*"
VALUE_SSESYRANAC = "(Y(*YHH(H*H0h"


def _setUpResponses(mock):
    mock.register_uri(
        "GET",
        URL_LOGIN_PAGE,
        status_code=200,
        cookies={
            COOKIE_XSRF_TOKEN: VALUE_XSRF_TOKEN,
            COOKIE_SSESYRANAC: VALUE_SSESYRANAC,
        })

    mock.register_uri(
        "POST",
        URL_LOGIN_API,
        text=load_fixture("canary_login.json"))

    mock.register_uri(
        "GET",
        URL_ME_API.format("foo@bar.org"),
        text=load_fixture("canary_me.json"))

    mock.register_uri(
        "GET",
        URL_LOCATIONS_API,
        text=load_fixture("canary_locations.json"))

    mock.register_uri(
        "GET",
        URL_READINGS_API.format(40001, "canary"),
        text=load_fixture("canary_readings_40001.json"))

    mock.register_uri(
        "GET",
        URL_READINGS_API.format(40003, "canary"),
        text=load_fixture("canary_readings_40003.json"))

    mock.register_uri(
        "GET",
        URL_ENTRIES_API.format(30002, "motion", 6),
        text=load_fixture("canary_entries_40001.json"))

    mock.register_uri(
        "GET",
        URL_ENTRIES_API.format(30001, "motion", 6),
        text="[]")


class TestCanary(unittest.TestCase):
    """Tests the Canary component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = copy.deepcopy(VALID_CONFIG)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test the setup."""
        _setUpResponses(mock)
        response = canary.setup(self.hass, self.config)
        self.assertTrue(response)

    @requests_mock.Mocker()
    def test_setup_component_no_login(self, mock):
        """Test the setup when no login is configured."""
        _setUpResponses(mock)
        conf = self.config
        del conf["canary"]["username"]
        assert not setup.setup_component(self.hass, canary.DOMAIN, conf)

    @requests_mock.Mocker()
    def test_setup_component_no_pwd(self, mock):
        """Test the setup when no password is configured."""
        _setUpResponses(mock)
        conf = self.config
        del conf["canary"]["password"]
        assert not setup.setup_component(self.hass, canary.DOMAIN, conf)
