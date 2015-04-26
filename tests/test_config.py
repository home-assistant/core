"""
tests.test_config
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests config utils.
"""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import unittest.mock as mock
import os

from homeassistant import DOMAIN, HomeAssistantError
import homeassistant.util as util
import homeassistant.config as config_util
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_TEMPERATURE_UNIT, CONF_NAME,
    CONF_TIME_ZONE)

from helpers import get_test_config_dir

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
CONF_PATH = os.path.join(CONFIG_DIR, config_util.CONF_CONFIG_FILE)


def create_file(path):
    """ Creates an empty file. """
    with open(path, 'w'):
        pass


def mock_detect_location_info():
    """ Mock implementation of util.detect_location_info. """
    return util.LocationInfo(
        ip='1.1.1.1',
        country_code='US',
        country_name='United States',
        region_code='CA',
        region_name='California',
        city='San Diego',
        zip_code='92122',
        time_zone='America/Los_Angeles',
        latitude='2.0',
        longitude='1.0',
        use_fahrenheit=True,
    )


class TestConfig(unittest.TestCase):
    """ Test the config utils. """

    def tearDown(self):  # pylint: disable=invalid-name
        """ Clean up. """
        for path in (YAML_PATH, CONF_PATH):
            if os.path.isfile(path):
                os.remove(path)

    def test_create_default_config(self):
        """ Test creationg of default config. """

        config_util.create_default_config(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))

    def test_find_config_file_yaml(self):
        """ Test if it finds a YAML config file. """

        create_file(YAML_PATH)

        self.assertEqual(YAML_PATH, config_util.find_config_file(CONFIG_DIR))

    def test_find_config_file_conf(self):
        """ Test if it finds the old CONF config file. """

        create_file(CONF_PATH)

        self.assertEqual(CONF_PATH, config_util.find_config_file(CONFIG_DIR))

    def test_find_config_file_prefers_yaml_over_conf(self):
        """ Test if find config prefers YAML over CONF if both exist. """

        create_file(YAML_PATH)
        create_file(CONF_PATH)

        self.assertEqual(YAML_PATH, config_util.find_config_file(CONFIG_DIR))

    def test_ensure_config_exists_creates_config(self):
        """ Test that calling ensure_config_exists creates a new config file if
            none exists. """

        config_util.ensure_config_exists(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))

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

    def test_load_config_loads_conf_config(self):
        """ Test correct YAML config loading. """
        create_file(CONF_PATH)

        self.assertEqual({}, config_util.load_config_file(CONF_PATH))

    def test_conf_config_file(self):
        """ Test correct CONF config loading. """
        with open(CONF_PATH, 'w') as f:
            f.write('[ha]\ntime_zone=America/Los_Angeles')

        self.assertEqual({'ha': {'time_zone': 'America/Los_Angeles'}},
                         config_util.load_conf_config_file(CONF_PATH))

    def test_create_default_config_detect_location(self):
        """ Test that detect location sets the correct config keys. """
        with mock.patch('homeassistant.util.detect_location_info',
                        mock_detect_location_info):
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

    def test_create_default_config_returns_none_if_write_error(self):
        """
        Test that writing default config to non existing folder returns None.
        """
        self.assertIsNone(
            config_util.create_default_config(
                os.path.join(CONFIG_DIR, 'non_existing_dir/'), False))
