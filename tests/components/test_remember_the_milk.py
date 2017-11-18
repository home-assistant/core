"""Tests for the Remember The Milk component."""

import logging
import unittest
from unittest.mock import patch, mock_open, Mock

import homeassistant.components.remember_the_milk as rtm

from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestConfiguration(unittest.TestCase):
    """Basic tests for the class RememberTheMilkConfiguration."""

    def setUp(self):
        """Set up test home assistant main loop."""
        self.hass = get_test_home_assistant()
        self.profile = "myprofile"
        self.token = "mytoken"
        self.json_string = '{"myprofile": {"token": "mytoken"}}'

    def tearDown(self):
        """Exit home assistant."""
        self.hass.stop()

    def test_create_new(self):
        """Test creating a new config file."""
        with patch("builtins.open", mock_open()), \
                patch("os.path.isfile", Mock(return_value=False)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
            config.set_token(self.profile, self.token)
        self.assertEqual(config.get_token(self.profile), self.token)

    def test_load_config(self):
        """Test loading an existing token from the file."""
        with patch("builtins.open", mock_open(read_data=self.json_string)), \
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        self.assertEqual(config.get_token(self.profile), self.token)

    def test_invalid_data(self):
        """Test starts with invalid data and should not raise an exception."""
        with patch("builtins.open",
                   mock_open(read_data='random charachters')),\
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        self.assertIsNotNone(config)
