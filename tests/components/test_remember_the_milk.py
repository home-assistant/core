"""Tests for the Remember The Milk component."""

import unittest
import logging
import os
import homeassistant.components.remember_the_milk as rtm
from unittest.mock import patch, mock_open, Mock
from tests.common import get_test_home_assistant

_LOGGER = logging.getLogger(__name__)


class TestConfiguration(unittest.TestCase):
    """Basic tests for the class RememberTheMilkConfiguration."""

    @staticmethod
    def _delete_config_file():
        if os.path.exists(rtm.CONFIG_FILE_NAME):
            os.remove(rtm.CONFIG_FILE_NAME)

    def test_create_new(self):
        """Test creating a new config file and reading data back."""
        profile = "myprofile"
        token = "mytoken"
        hass = get_test_home_assistant()
        self._delete_config_file()

        config = rtm.RememberTheMilkConfiguration(hass)
        config.set_token(profile, token)
        self.assertEqual(config.get_token(profile), token)
        self.assertTrue(os.path.exists(rtm.CONFIG_FILE_NAME))

        del config

        config = rtm.RememberTheMilkConfiguration(hass)
        self.assertEqual(config.get_token(profile), token)

    def test_invalid_data(self):
        """Test starts with invalid data and should not raise an exception."""

        with patch("builtins.open", mock_open(read_data='random charachters')), \
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(get_test_home_assistant())
        self.assertIsNotNone(config)
