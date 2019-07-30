"""Tests for the Remember The Milk component."""

import logging
import json
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
        self.json_string = json.dumps(
            {"myprofile": {
                "token": "mytoken",
                "id_map": {"1234": {
                    "list_id": "0",
                    "timeseries_id": "1",
                    "task_id": "2"
                }}
            }
            })

    def tearDown(self):
        """Exit home assistant."""
        self.hass.stop()

    def test_create_new(self):
        """Test creating a new config file."""
        with patch("builtins.open", mock_open()), \
                patch("os.path.isfile", Mock(return_value=False)), \
                patch.object(rtm.RememberTheMilkConfiguration, 'save_config'):
            config = rtm.RememberTheMilkConfiguration(self.hass)
            config.set_token(self.profile, self.token)
        assert config.get_token(self.profile) == self.token

    def test_load_config(self):
        """Test loading an existing token from the file."""
        with patch("builtins.open", mock_open(read_data=self.json_string)), \
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        assert config.get_token(self.profile) == self.token

    def test_invalid_data(self):
        """Test starts with invalid data and should not raise an exception."""
        with patch("builtins.open",
                   mock_open(read_data='random characters')),\
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        assert config is not None

    def test_id_map(self):
        """Test the hass to rtm task is mapping."""
        hass_id = "hass-id-1234"
        list_id = "mylist"
        timeseries_id = "my_timeseries"
        rtm_id = "rtm-id-4567"
        with patch("builtins.open", mock_open()), \
                patch("os.path.isfile", Mock(return_value=False)), \
                patch.object(rtm.RememberTheMilkConfiguration, 'save_config'):
            config = rtm.RememberTheMilkConfiguration(self.hass)

            assert config.get_rtm_id(self.profile, hass_id) is None
            config.set_rtm_id(self.profile, hass_id, list_id, timeseries_id,
                              rtm_id)
            assert (list_id, timeseries_id, rtm_id) == \
                config.get_rtm_id(self.profile, hass_id)
            config.delete_rtm_id(self.profile, hass_id)
            assert config.get_rtm_id(self.profile, hass_id) is None

    def test_load_key_map(self):
        """Test loading an existing key map from the file."""
        with patch("builtins.open", mock_open(read_data=self.json_string)), \
                patch("os.path.isfile", Mock(return_value=True)):
            config = rtm.RememberTheMilkConfiguration(self.hass)
        assert ('0', '1', '2',) == \
            config.get_rtm_id(self.profile, "1234")
