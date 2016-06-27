"""Test config utils."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import unittest.mock as mock
import os

import pytest
from voluptuous import MultipleInvalid

from homeassistant.core import DOMAIN, HomeAssistantError
import homeassistant.config as config_util
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_TEMPERATURE_UNIT, CONF_NAME,
    CONF_TIME_ZONE, CONF_ELEVATION)
from homeassistant.util import location as location_util

from tests.common import get_test_config_dir, load_fixture

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)


def create_file(path):
    """Create an empty file."""
    with open(path, 'w'):
        pass


class TestConfig(unittest.TestCase):
    """Test the configutils."""

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up."""
        if os.path.isfile(YAML_PATH):
            os.remove(YAML_PATH)

    def test_create_default_config(self):
        """Test creation of default config."""
        config_util.create_default_config(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))

    def test_find_config_file_yaml(self):
        """Test if it finds a YAML config file."""
        create_file(YAML_PATH)

        self.assertEqual(YAML_PATH, config_util.find_config_file(CONFIG_DIR))

    @mock.patch('builtins.print')
    def test_ensure_config_exists_creates_config(self, mock_print):
        """Test that calling ensure_config_exists.

        If not creates a new config file.
        """
        config_util.ensure_config_exists(CONFIG_DIR, False)

        self.assertTrue(os.path.isfile(YAML_PATH))
        self.assertTrue(mock_print.called)

    def test_ensure_config_exists_uses_existing_config(self):
        """Test that calling ensure_config_exists uses existing config."""
        create_file(YAML_PATH)
        config_util.ensure_config_exists(CONFIG_DIR, False)

        with open(YAML_PATH) as f:
            content = f.read()

        # File created with create_file are empty
        self.assertEqual('', content)

    def test_load_yaml_config_converts_empty_files_to_dict(self):
        """Test that loading an empty file returns an empty dict."""
        create_file(YAML_PATH)

        self.assertIsInstance(
            config_util.load_yaml_config_file(YAML_PATH), dict)

    def test_load_yaml_config_raises_error_if_not_dict(self):
        """Test error raised when YAML file is not a dict."""
        with open(YAML_PATH, 'w') as f:
            f.write('5')

        with self.assertRaises(HomeAssistantError):
            config_util.load_yaml_config_file(YAML_PATH)

    def test_load_yaml_config_raises_error_if_malformed_yaml(self):
        """Test error raised if invalid YAML."""
        with open(YAML_PATH, 'w') as f:
            f.write(':')

        with self.assertRaises(HomeAssistantError):
            config_util.load_yaml_config_file(YAML_PATH)

    def test_load_yaml_config_raises_error_if_unsafe_yaml(self):
        """Test error raised if unsafe YAML."""
        with open(YAML_PATH, 'w') as f:
            f.write('hello: !!python/object/apply:os.system')

        with self.assertRaises(HomeAssistantError):
            config_util.load_yaml_config_file(YAML_PATH)

    def test_load_yaml_config_preserves_key_order(self):
        """Test removal of library."""
        with open(YAML_PATH, 'w') as f:
            f.write('hello: 0\n')
            f.write('world: 1\n')

        self.assertEqual(
            [('hello', 0), ('world', 1)],
            list(config_util.load_yaml_config_file(YAML_PATH).items()))

    @mock.patch('homeassistant.util.location.detect_location_info',
                return_value=location_util.LocationInfo(
                    '0.0.0.0', 'US', 'United States', 'CA', 'California',
                    'San Diego', '92122', 'America/Los_Angeles', 32.8594,
                    -117.2073, 101, True))
    @mock.patch('builtins.print')
    def test_create_default_config_detect_location(self, m, mock_print):
        """Test that detect location sets the correct config keys."""
        m.get(location_util.FREEGEO_API,
              text=load_fixture('freegeoip.io.json'))

        config_util.ensure_config_exists(CONFIG_DIR)

        config = config_util.load_yaml_config_file(YAML_PATH)

        self.assertIn(DOMAIN, config)

        ha_conf = config[DOMAIN]

        expected_values = {
            CONF_LATITUDE: 32.8594,
            CONF_LONGITUDE: -117.2073,
            CONF_ELEVATION: 101,
            CONF_TEMPERATURE_UNIT: 'F',
            CONF_NAME: 'Home',
            CONF_TIME_ZONE: 'America/Los_Angeles'
        }

        assert expected_values == ha_conf
        assert mock_print.called

    @mock.patch('builtins.print')
    def test_create_default_config_returns_none_if_write_error(self,
                                                               mock_print):
        """Test the writing of a default configuration.

        Non existing folder returns None.
        """
        self.assertIsNone(
            config_util.create_default_config(
                os.path.join(CONFIG_DIR, 'non_existing_dir/'), False))
        self.assertTrue(mock_print.called)

    def test_core_config_schema(self):
        for value in (
            {'temperature_unit': 'K'},
            {'time_zone': 'non-exist'},
            {'latitude': '91'},
            {'longitude': -181},
            {'customize': 'bla'},
            {'customize': {'invalid_entity_id': {}}},
            {'customize': {'light.sensor': 100}},
        ):
            with pytest.raises(MultipleInvalid):
                config_util.CORE_CONFIG_SCHEMA(value)

        config_util.CORE_CONFIG_SCHEMA({
            'name': 'Test name',
            'latitude': '-23.45',
            'longitude': '123.45',
            'temperature_unit': 'c',
            'customize': {
                'sensor.temperature': {
                    'hidden': True,
                },
            },
        })
