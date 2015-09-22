"""
tests.test_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests config utils.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import unittest.mock as mock
import os

from homeassistant.core import DOMAIN, HomeAssistantError
import homeassistant.config as config_util
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_TEMPERATURE_UNIT, CONF_NAME,
    CONF_TIME_ZONE)

from tests.common import get_test_config_dir, mock_detect_location_info

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)


def create_file(path):
    """ Creates an empty file. """
    with open(path, 'w'):
        pass


class TestConfig(unittest.TestCase):
    """ Test the config utils. """

    def tearDown(self):  # pylint: disable=invalid-name
        """ Clean up. """
        if os.path.isfile(YAML_PATH):
            os.remove(YAML_PATH)

    def test_create_default_config(self):
        """ Test creationg of default config. """

        config_util.create_default_config(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))

    def test_find_config_file_yaml(self):
        """ Test if it finds a YAML config file. """

        create_file(YAML_PATH)

        self.assertEqual(YAML_PATH, config_util.find_config_file(CONFIG_DIR))

    @mock.patch('builtins.print')
    def test_ensure_config_exists_creates_config(self, mock_print):
        """ Test that calling ensure_config_exists creates a new config file if
            none exists. """

        config_util.ensure_config_exists(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))
        self.assertTrue(mock_print.called)

    def test_ensure_config_exists_uses_existing_config(self):
        """ Test that calling ensure_config_exists uses existing config. """

        create_file(YAML_PATH)
        config_util.ensure_config_exists(CONFIG_DIR, False)

        with open(YAML_PATH) as f:
            content = f.read()

        # File created with create_file are empty
        self.assertEqual('', content)

    def test_load_yaml_config_converts_empty_files_to_dict(self):
        """ Test that loading an empty file returns an empty dict. """
        create_file(YAML_PATH)

        self.assertIsInstance(
            config_util.load_yaml_config_file(YAML_PATH), dict)

    def test_load_yaml_config_raises_error_if_not_dict(self):
        """ Test error raised when YAML file is not a dict. """
        with open(YAML_PATH, 'w') as f:
            f.write('5')

        with self.assertRaises(HomeAssistantError):
            config_util.load_yaml_config_file(YAML_PATH)

    def test_load_yaml_config_raises_error_if_malformed_yaml(self):
        """ Test error raised if invalid YAML. """
        with open(YAML_PATH, 'w') as f:
            f.write(':')

        with self.assertRaises(HomeAssistantError):
            config_util.load_yaml_config_file(YAML_PATH)

    def test_load_config_loads_yaml_config(self):
        """ Test correct YAML config loading. """
        with open(YAML_PATH, 'w') as f:
            f.write('hello: world')

        self.assertEqual({'hello': 'world'},
                         config_util.load_config_file(YAML_PATH))

    @mock.patch('homeassistant.util.location.detect_location_info',
                mock_detect_location_info)
    @mock.patch('builtins.print')
    def test_create_default_config_detect_location(self, mock_print):
        """ Test that detect location sets the correct config keys. """
        config_util.ensure_config_exists(CONFIG_DIR)

        config = config_util.load_config_file(YAML_PATH)

        self.assertIn(DOMAIN, config)

        ha_conf = config[DOMAIN]

        expected_values = {
            CONF_LATITUDE: 2.0,
            CONF_LONGITUDE: 1.0,
            CONF_TEMPERATURE_UNIT: 'F',
            CONF_NAME: 'Home',
            CONF_TIME_ZONE: 'America/Los_Angeles'
        }

        self.assertEqual(expected_values, ha_conf)
        self.assertTrue(mock_print.called)

    @mock.patch('builtins.print')
    def test_create_default_config_returns_none_if_write_error(self,
                                                               mock_print):
        """
        Test that writing default config to non existing folder returns None.
        """
        self.assertIsNone(
            config_util.create_default_config(
                os.path.join(CONFIG_DIR, 'non_existing_dir/'), False))
        self.assertTrue(mock_print.called)
