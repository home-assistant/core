"""The tests for the Vultr component."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

import requests_mock

from homeassistant import setup
import homeassistant.components.vultr as vultr

from tests.common import get_test_home_assistant, load_fixture

VALID_CONFIG = {"vultr": {"api_key": "ABCDEFG1234567"}}


class TestVultr(unittest.TestCase):
    """Tests the Vultr component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that we started."""
        self.hass.stop()

    @requests_mock.Mocker()
    def test_setup(self, mock):
        """Test successful setup."""
        with patch(
            "vultr.Vultr.server_list",
            return_value=json.loads(load_fixture("vultr_server_list.json")),
        ):
            response = vultr.setup(self.hass, self.config)
        assert response

    def test_setup_no_api_key(self):
        """Test failed setup with missing API Key."""
        conf = deepcopy(self.config)
        del conf["vultr"]["api_key"]
        assert not setup.setup_component(self.hass, vultr.DOMAIN, conf)
