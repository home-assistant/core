"""Test config utils."""
# pylint: disable=too-many-public-methods,protected-access
import os
import tempfile
import unittest
import unittest.mock as mock

import pytest
from voluptuous import MultipleInvalid

from homeassistant.core import DOMAIN, HomeAssistantError, Config
import homeassistant.config as config_util
from homeassistant.const import (
    CONF_LATITUDE, CONF_LONGITUDE, CONF_UNIT_SYSTEM, CONF_NAME,
    CONF_TIME_ZONE, CONF_ELEVATION, CONF_CUSTOMIZE, __version__,
    CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL, CONF_TEMPERATURE_UNIT)
from homeassistant.util import location as location_util, dt as dt_util
from homeassistant.helpers.entity import Entity

from tests.common import (
    get_test_config_dir, get_test_home_assistant)

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
VERSION_PATH = os.path.join(CONFIG_DIR, config_util.VERSION_FILE)
ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE


def create_file(path):
    """Create an empty file."""
    with open(path, 'w'):
        pass


class TestConfig(unittest.TestCase):
    """Test the configutils."""

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up."""
        dt_util.DEFAULT_TIME_ZONE = ORIG_TIMEZONE

        if os.path.isfile(YAML_PATH):
            os.remove(YAML_PATH)

        if os.path.isfile(VERSION_PATH):
            os.remove(VERSION_PATH)

        if hasattr(self, 'hass'):
            self.hass.stop()

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
                    -117.2073, True))
    @mock.patch('homeassistant.util.location.elevation', return_value=101)
    @mock.patch('builtins.print')
    def test_create_default_config_detect_location(self, mock_detect,
                                                   mock_elev, mock_print):
        """Test that detect location sets the correct config keys."""
        config_util.ensure_config_exists(CONFIG_DIR)

        config = config_util.load_yaml_config_file(YAML_PATH)

        self.assertIn(DOMAIN, config)

        ha_conf = config[DOMAIN]

        expected_values = {
            CONF_LATITUDE: 32.8594,
            CONF_LONGITUDE: -117.2073,
            CONF_ELEVATION: 101,
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
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
            {CONF_UNIT_SYSTEM: 'K'},
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
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_METRIC,
            'customize': {
                'sensor.temperature': {
                    'hidden': True,
                },
            },
        })

    def test_entity_customization(self):
        """Test entity customization through configuration."""
        self.hass = get_test_home_assistant()

        config = {CONF_LATITUDE: 50,
                  CONF_LONGITUDE: 50,
                  CONF_NAME: 'Test',
                  CONF_CUSTOMIZE: {'test.test': {'hidden': True}}}

        config_util.process_ha_core_config(self.hass, config)

        entity = Entity()
        entity.entity_id = 'test.test'
        entity.hass = self.hass
        entity.update_ha_state()

        self.hass.block_till_done()

        state = self.hass.states.get('test.test')

        assert state.attributes['hidden']

    def test_remove_lib_on_upgrade(self):
        """Test removal of library on upgrade."""
        with tempfile.TemporaryDirectory() as config_dir:
            version_path = os.path.join(config_dir, '.HA_VERSION')
            lib_dir = os.path.join(config_dir, 'deps')
            check_file = os.path.join(lib_dir, 'check')

            with open(version_path, 'wt') as outp:
                outp.write('0.7.0')

            os.mkdir(lib_dir)

            with open(check_file, 'w'):
                pass

            self.hass = get_test_home_assistant()
            self.hass.config.config_dir = config_dir

            assert os.path.isfile(check_file)
            config_util.process_ha_config_upgrade(self.hass)
            assert not os.path.isfile(check_file)

    def test_not_remove_lib_if_not_upgrade(self):
        """Test removal of library with no upgrade."""
        with tempfile.TemporaryDirectory() as config_dir:
            version_path = os.path.join(config_dir, '.HA_VERSION')
            lib_dir = os.path.join(config_dir, 'deps')
            check_file = os.path.join(lib_dir, 'check')

            with open(version_path, 'wt') as outp:
                outp.write(__version__)

            os.mkdir(lib_dir)

            with open(check_file, 'w'):
                pass

            self.hass = get_test_home_assistant()
            self.hass.config.config_dir = config_dir

            config_util.process_ha_config_upgrade(self.hass)

            assert os.path.isfile(check_file)

    def test_loading_configuration(self):
        """Test loading core config onto hass object."""
        config = Config()
        hass = mock.Mock(config=config)

        config_util.process_ha_core_config(hass, {
            'latitude': 60,
            'longitude': 50,
            'elevation': 25,
            'name': 'Huis',
            CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
            'time_zone': 'America/New_York',
        })

        assert config.latitude == 60
        assert config.longitude == 50
        assert config.elevation == 25
        assert config.location_name == 'Huis'
        assert config.units.name == CONF_UNIT_SYSTEM_IMPERIAL
        assert config.time_zone.zone == 'America/New_York'

    def test_loading_configuration_temperature_unit(self):
        """Test backward compatibility when loading core config."""
        config = Config()
        hass = mock.Mock(config=config)

        config_util.process_ha_core_config(hass, {
            'latitude': 60,
            'longitude': 50,
            'elevation': 25,
            'name': 'Huis',
            CONF_TEMPERATURE_UNIT: 'C',
            'time_zone': 'America/New_York',
        })

        assert config.latitude == 60
        assert config.longitude == 50
        assert config.elevation == 25
        assert config.location_name == 'Huis'
        assert config.units.name == CONF_UNIT_SYSTEM_METRIC
        assert config.time_zone.zone == 'America/New_York'

    @mock.patch('homeassistant.util.location.detect_location_info',
                return_value=location_util.LocationInfo(
                    '0.0.0.0', 'US', 'United States', 'CA', 'California',
                    'San Diego', '92122', 'America/Los_Angeles', 32.8594,
                    -117.2073, True))
    @mock.patch('homeassistant.util.location.elevation', return_value=101)
    def test_discovering_configuration(self, mock_detect, mock_elevation):
        """Test auto discovery for missing core configs."""
        config = Config()
        hass = mock.Mock(config=config)

        config_util.process_ha_core_config(hass, {})

        assert config.latitude == 32.8594
        assert config.longitude == -117.2073
        assert config.elevation == 101
        assert config.location_name == 'San Diego'
        assert config.units.name == CONF_UNIT_SYSTEM_METRIC
        assert config.units.is_metric
        assert config.time_zone.zone == 'America/Los_Angeles'

    @mock.patch('homeassistant.util.location.detect_location_info',
                return_value=None)
    @mock.patch('homeassistant.util.location.elevation', return_value=0)
    def test_discovering_configuration_auto_detect_fails(self, mock_detect,
                                                         mock_elevation):
        """Test config remains unchanged if discovery fails."""
        config = Config()
        hass = mock.Mock(config=config)

        config_util.process_ha_core_config(hass, {})

        blankConfig = Config()
        assert config.latitude == blankConfig.latitude
        assert config.longitude == blankConfig.longitude
        assert config.elevation == blankConfig.elevation
        assert config.location_name == blankConfig.location_name
        assert config.units == blankConfig.units
        assert config.time_zone == blankConfig.time_zone
