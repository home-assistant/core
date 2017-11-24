"""The tests for the Canary component."""
import unittest
from unittest.mock import patch

import homeassistant.components.canary as canary
from canary.api import Location, Mode
from tests.common import (
    get_test_home_assistant)

MODES_BY_NAME = {
    "home": Mode({"id": 1, "name": "Home", "resource_uri": "/v1/home"}),
    "away": Mode({"id": 2, "name": "Away", "resource_uri": "/v1/away"}),
    "night": Mode({"id": 3, "name": "Night", "resource_uri": "/v1/night"}),
}

API_LOCATIONS = [Location({
    "id": 1,
    "name": "Home",
    "is_private": False,
    "mode": {"name": "away"},
    "current_mode": {"name": "armed"},
    "devices": [
        {
            "id": 20,
            "name": "Dining Room",
            "online": True,
            "device_type": {},
        },
        {
            "id": 21,
            "name": "Front Yard",
            "online": False,
            "device_type": {},
        }
    ],
    "customers": [{
        "id": 30,
        "first_name": "",
        "last_name": "",
        "celsius": True,
    }],
}, MODES_BY_NAME), Location({
    "id": 2,
    "name": "Vacation Home",
    "is_private": True,
    "mode": {"name": "home"},
    "current_mode": {"name": "standby"},
    "devices": [{
        "id": 22,
        "name": "Den",
        "online": True,
        "device_type": {},
    }],
    "customers": [{
        "id": 31,
        "first_name": "",
        "last_name": "",
        "celsius": False,
    }],
}, MODES_BY_NAME)]


class TestCanary(unittest.TestCase):
    """Tests the Canary component."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    @patch('homeassistant.components.canary.CanaryData.update')
    @patch('canary.api.Api.login')
    def test_setup_with_valid_config(self, mock_login, mock_update):
        """Test setup component."""
        config = {
            "canary": {
                "username": "foo@bar.org",
                "password": "bar",
            }
        }

        self.assertTrue(canary.setup(self.hass, config))

        mock_update.assert_called_once()
        mock_login.assert_called_once()

    def test_setup_with_missing_password(self):
        """Test setup component."""
        config = {
            "canary": {
                "username": "foo@bar.org",
            }
        }

        self.assertFalse(canary.setup(self.hass, config))

    def test_setup_with_missing_username(self):
        """Test setup component."""
        config = {
            "canary": {
                "password": "bar",
            }
        }

        self.assertFalse(canary.setup(self.hass, config))
