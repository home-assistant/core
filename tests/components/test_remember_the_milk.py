"""Tests for the Remember The Milk component."""

import unittest
import logging
import os
import homeassistant.components.remember_the_milk as rtm

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

        self._delete_config_file()

        config = rtm.RememberTheMilkConfiguration()
        config.set_token(profile, token)
        self.assertEqual(config.get_token(profile), token)
        self.assertTrue(os.path.exists(rtm.CONFIG_FILE_NAME))

        del config

        config = rtm.RememberTheMilkConfiguration()
        self.assertEqual(config.get_token(profile), token)

    def test_invalid_data(self):
        """Test starts with invalid data and should not raise an exception."""
        with open(rtm.CONFIG_FILE_NAME, "w") as config_file:
            config_file.write('random charachters')

        config = rtm.RememberTheMilkConfiguration()
        self.assertIsNotNone(config)
