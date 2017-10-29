"""Tests for the Remember The Milk component."""

import logging
import os
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

    def tearDown(self):
        """Exit home assistant."""
        self.hass.stop()

    def test_create_new(self):
        """Test creating a new config file and reading data back."""
        profile = "myprofile"
        token = "mytoken"

        config = rtm.RememberTheMilkConfiguration(self.hass)
        config.set_token(profile, token)
        self.assertEqual(config.get_token(profile), token)
        self.assertTrue(os.path.exists(rtm.CONFIG_FILE_NAME))

        del config

        config = rtm.RememberTheMilkConfiguration(self.hass)
        self.assertEqual(config.get_token(profile), token)

    def test_invalid_data(self):
        """Test starts with invalid data and should not raise an exception."""

        with patch("builtins.open", mock_open(read_data='random charachters')), \
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        self.assertIsNotNone(config)
