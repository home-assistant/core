"""Test config utils."""
# pylint: disable=protected-access
import asyncio
import os
import unittest
import unittest.mock as mock
from collections import OrderedDict

import pytest
from voluptuous import MultipleInvalid, Invalid

from homeassistant.core import DOMAIN, HomeAssistantError, Config
import homeassistant.config as config_util
from homeassistant.const import (
    ATTR_FRIENDLY_NAME, ATTR_HIDDEN, ATTR_ASSUMED_STATE,
    CONF_LATITUDE, CONF_LONGITUDE, CONF_UNIT_SYSTEM, CONF_NAME,
    CONF_TIME_ZONE, CONF_ELEVATION, CONF_CUSTOMIZE, __version__,
    CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL, CONF_TEMPERATURE_UNIT,
    CONF_AUTH_PROVIDERS, CONF_AUTH_MFA_MODULES)
from homeassistant.util import location as location_util, dt as dt_util
from homeassistant.util.yaml import SECRET_YAML
from homeassistant.util.async_ import run_coroutine_threadsafe
from homeassistant.helpers.entity import Entity
from homeassistant.components.config.group import (
    CONFIG_PATH as GROUP_CONFIG_PATH)
from homeassistant.components.config.automation import (
    CONFIG_PATH as AUTOMATIONS_CONFIG_PATH)
from homeassistant.components.config.script import (
    CONFIG_PATH as SCRIPTS_CONFIG_PATH)
from homeassistant.components.config.customize import (
    CONFIG_PATH as CUSTOMIZE_CONFIG_PATH)
import homeassistant.scripts.check_config as check_config

from tests.common import get_test_config_dir, get_test_home_assistant

CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
SECRET_PATH = os.path.join(CONFIG_DIR, SECRET_YAML)
VERSION_PATH = os.path.join(CONFIG_DIR, config_util.VERSION_FILE)
GROUP_PATH = os.path.join(CONFIG_DIR, GROUP_CONFIG_PATH)
AUTOMATIONS_PATH = os.path.join(CONFIG_DIR, AUTOMATIONS_CONFIG_PATH)
SCRIPTS_PATH = os.path.join(CONFIG_DIR, SCRIPTS_CONFIG_PATH)
CUSTOMIZE_PATH = os.path.join(CONFIG_DIR, CUSTOMIZE_CONFIG_PATH)
ORIG_TIMEZONE = dt_util.DEFAULT_TIME_ZONE


def create_file(path):
    """Create an empty file."""
    with open(path, 'w'):
        pass


class TestConfig(unittest.TestCase):
    """Test the configutils."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Initialize a test Home Assistant instance."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Clean up."""
        dt_util.DEFAULT_TIME_ZONE = ORIG_TIMEZONE

        if os.path.isfile(YAML_PATH):
            os.remove(YAML_PATH)

        if os.path.isfile(SECRET_PATH):
            os.remove(SECRET_PATH)

        if os.path.isfile(VERSION_PATH):
            os.remove(VERSION_PATH)

        if os.path.isfile(GROUP_PATH):
            os.remove(GROUP_PATH)

        if os.path.isfile(AUTOMATIONS_PATH):
            os.remove(AUTOMATIONS_PATH)

        if os.path.isfile(SCRIPTS_PATH):
            os.remove(SCRIPTS_PATH)

        if os.path.isfile(CUSTOMIZE_PATH):
            os.remove(CUSTOMIZE_PATH)

        self.hass.stop()

    # pylint: disable=no-self-use
    def test_create_default_config(self):
        """Test creation of default config."""
        config_util.create_default_config(CONFIG_DIR, False)

        assert os.path.isfile(YAML_PATH)
        assert os.path.isfile(SECRET_PATH)
        assert os.path.isfile(VERSION_PATH)
        assert os.path.isfile(GROUP_PATH)
        assert os.path.isfile(AUTOMATIONS_PATH)
        assert os.path.isfile(CUSTOMIZE_PATH)

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
            f.write('hello: 2\n')
            f.write('world: 1\n')

        self.assertEqual(
            [('hello', 2), ('world', 1)],
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
            CONF_TIME_ZONE: 'America/Los_Angeles',
            CONF_CUSTOMIZE: OrderedDict(),
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

    # pylint: disable=no-self-use
    def test_core_config_schema(self):
        """Test core config schema."""
        for value in (
                {CONF_UNIT_SYSTEM: 'K'},
                {'time_zone': 'non-exist'},
                {'latitude': '91'},
                {'longitude': -181},
                {'customize': 'bla'},
                {'customize': {'light.sensor': 100}},
                {'customize': {'entity_id': []}},
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

    def test_customize_dict_schema(self):
        """Test basic customize config validation."""
        values = (
            {ATTR_FRIENDLY_NAME: None},
            {ATTR_HIDDEN: '2'},
            {ATTR_ASSUMED_STATE: '2'},
        )

        for val in values:
            print(val)
            with pytest.raises(MultipleInvalid):
                config_util.CUSTOMIZE_DICT_SCHEMA(val)

        assert config_util.CUSTOMIZE_DICT_SCHEMA({
            ATTR_FRIENDLY_NAME: 2,
            ATTR_HIDDEN: '1',
            ATTR_ASSUMED_STATE: '0',
        }) == {
            ATTR_FRIENDLY_NAME: '2',
            ATTR_HIDDEN: True,
            ATTR_ASSUMED_STATE: False
        }

    def test_customize_glob_is_ordered(self):
        """Test that customize_glob preserves order."""
        conf = config_util.CORE_CONFIG_SCHEMA(
            {'customize_glob': OrderedDict()})
        self.assertIsInstance(conf['customize_glob'], OrderedDict)

    def _compute_state(self, config):
        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(self.hass, config),
            self.hass.loop).result()

        entity = Entity()
        entity.entity_id = 'test.test'
        entity.hass = self.hass
        entity.schedule_update_ha_state()

        self.hass.block_till_done()

        return self.hass.states.get('test.test')

    def test_entity_customization(self):
        """Test entity customization through configuration."""
        config = {CONF_LATITUDE: 50,
                  CONF_LONGITUDE: 50,
                  CONF_NAME: 'Test',
                  CONF_CUSTOMIZE: {'test.test': {'hidden': True}}}

        state = self._compute_state(config)

        assert state.attributes['hidden']

    @mock.patch('homeassistant.config.shutil')
    @mock.patch('homeassistant.config.os')
    def test_remove_lib_on_upgrade(self, mock_os, mock_shutil):
        """Test removal of library on upgrade from before 0.50."""
        ha_version = '0.49.0'
        mock_os.path.isdir = mock.Mock(return_value=True)
        mock_open = mock.mock_open()
        with mock.patch('homeassistant.config.open', mock_open, create=True):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            opened_file.readline.return_value = ha_version
            self.hass.config.path = mock.Mock()
            config_util.process_ha_config_upgrade(self.hass)
            hass_path = self.hass.config.path.return_value

            self.assertEqual(mock_os.path.isdir.call_count, 1)
            self.assertEqual(
                mock_os.path.isdir.call_args, mock.call(hass_path)
            )
            self.assertEqual(mock_shutil.rmtree.call_count, 1)
            self.assertEqual(
                mock_shutil.rmtree.call_args, mock.call(hass_path)
            )

    def test_process_config_upgrade(self):
        """Test update of version on upgrade."""
        ha_version = '0.8.0'

        mock_open = mock.mock_open()
        with mock.patch('homeassistant.config.open', mock_open, create=True):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            opened_file.readline.return_value = ha_version

            config_util.process_ha_config_upgrade(self.hass)

            self.assertEqual(opened_file.write.call_count, 1)
            self.assertEqual(
                opened_file.write.call_args, mock.call(__version__)
            )

    def test_config_upgrade_same_version(self):
        """Test no update of version on no upgrade."""
        ha_version = __version__

        mock_open = mock.mock_open()
        with mock.patch('homeassistant.config.open', mock_open, create=True):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            opened_file.readline.return_value = ha_version

            config_util.process_ha_config_upgrade(self.hass)

            assert opened_file.write.call_count == 0

    def test_config_upgrade_no_file(self):
        """Test update of version on upgrade, with no version file."""
        mock_open = mock.mock_open()
        mock_open.side_effect = [FileNotFoundError(), mock.DEFAULT]
        with mock.patch('homeassistant.config.open', mock_open, create=True):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            config_util.process_ha_config_upgrade(self.hass)
            self.assertEqual(opened_file.write.call_count, 1)
            self.assertEqual(
                opened_file.write.call_args, mock.call(__version__))

    @mock.patch('homeassistant.config.shutil')
    @mock.patch('homeassistant.config.os')
    def test_migrate_file_on_upgrade(self, mock_os, mock_shutil):
        """Test migrate of config files on upgrade."""
        ha_version = '0.7.0'

        mock_os.path.isdir = mock.Mock(return_value=True)

        mock_open = mock.mock_open()

        def _mock_isfile(filename):
            return True

        with mock.patch('homeassistant.config.open', mock_open, create=True), \
                mock.patch(
                    'homeassistant.config.os.path.isfile', _mock_isfile):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            opened_file.readline.return_value = ha_version

            self.hass.config.path = mock.Mock()

            config_util.process_ha_config_upgrade(self.hass)

        assert mock_os.rename.call_count == 1

    @mock.patch('homeassistant.config.shutil')
    @mock.patch('homeassistant.config.os')
    def test_migrate_no_file_on_upgrade(self, mock_os, mock_shutil):
        """Test not migrating config files on upgrade."""
        ha_version = '0.7.0'

        mock_os.path.isdir = mock.Mock(return_value=True)

        mock_open = mock.mock_open()

        def _mock_isfile(filename):
            return False

        with mock.patch('homeassistant.config.open', mock_open, create=True), \
                mock.patch(
                    'homeassistant.config.os.path.isfile', _mock_isfile):
            opened_file = mock_open.return_value
            # pylint: disable=no-member
            opened_file.readline.return_value = ha_version

            self.hass.config.path = mock.Mock()

            config_util.process_ha_config_upgrade(self.hass)

        assert mock_os.rename.call_count == 0

    def test_loading_configuration(self):
        """Test loading core config onto hass object."""
        self.hass.config = mock.Mock()

        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(self.hass, {
                'latitude': 60,
                'longitude': 50,
                'elevation': 25,
                'name': 'Huis',
                CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
                'time_zone': 'America/New_York',
                'whitelist_external_dirs': '/tmp',
            }), self.hass.loop).result()

        assert self.hass.config.latitude == 60
        assert self.hass.config.longitude == 50
        assert self.hass.config.elevation == 25
        assert self.hass.config.location_name == 'Huis'
        assert self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL
        assert self.hass.config.time_zone.zone == 'America/New_York'
        assert len(self.hass.config.whitelist_external_dirs) == 2
        assert '/tmp' in self.hass.config.whitelist_external_dirs

    def test_loading_configuration_temperature_unit(self):
        """Test backward compatibility when loading core config."""
        self.hass.config = mock.Mock()

        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(self.hass, {
                'latitude': 60,
                'longitude': 50,
                'elevation': 25,
                'name': 'Huis',
                CONF_TEMPERATURE_UNIT: 'C',
                'time_zone': 'America/New_York',
            }), self.hass.loop).result()

        assert self.hass.config.latitude == 60
        assert self.hass.config.longitude == 50
        assert self.hass.config.elevation == 25
        assert self.hass.config.location_name == 'Huis'
        assert self.hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
        assert self.hass.config.time_zone.zone == 'America/New_York'

    def test_loading_configuration_from_packages(self):
        """Test loading packages config onto hass object config."""
        self.hass.config = mock.Mock()

        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(self.hass, {
                'latitude': 39,
                'longitude': -1,
                'elevation': 500,
                'name': 'Huis',
                CONF_TEMPERATURE_UNIT: 'C',
                'time_zone': 'Europe/Madrid',
                'packages': {
                    'package_1': {'wake_on_lan': None},
                    'package_2': {'light': {'platform': 'hue'},
                                  'media_extractor': None,
                                  'sun': None}},
            }), self.hass.loop).result()

        # Empty packages not allowed
        with pytest.raises(MultipleInvalid):
            run_coroutine_threadsafe(
                config_util.async_process_ha_core_config(self.hass, {
                    'latitude': 39,
                    'longitude': -1,
                    'elevation': 500,
                    'name': 'Huis',
                    CONF_TEMPERATURE_UNIT: 'C',
                    'time_zone': 'Europe/Madrid',
                    'packages': {'empty_package': None},
                }), self.hass.loop).result()

    @mock.patch('homeassistant.util.location.detect_location_info',
                autospec=True, return_value=location_util.LocationInfo(
                    '0.0.0.0', 'US', 'United States', 'CA', 'California',
                    'San Diego', '92122', 'America/Los_Angeles', 32.8594,
                    -117.2073, True))
    @mock.patch('homeassistant.util.location.elevation',
                autospec=True, return_value=101)
    def test_discovering_configuration(self, mock_detect, mock_elevation):
        """Test auto discovery for missing core configs."""
        self.hass.config.latitude = None
        self.hass.config.longitude = None
        self.hass.config.elevation = None
        self.hass.config.location_name = None
        self.hass.config.time_zone = None

        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(
                self.hass, {}), self.hass.loop
            ).result()

        assert self.hass.config.latitude == 32.8594
        assert self.hass.config.longitude == -117.2073
        assert self.hass.config.elevation == 101
        assert self.hass.config.location_name == 'San Diego'
        assert self.hass.config.units.name == CONF_UNIT_SYSTEM_METRIC
        assert self.hass.config.units.is_metric
        assert self.hass.config.time_zone.zone == 'America/Los_Angeles'

    @mock.patch('homeassistant.util.location.detect_location_info',
                autospec=True, return_value=None)
    @mock.patch('homeassistant.util.location.elevation', return_value=0)
    def test_discovering_configuration_auto_detect_fails(self, mock_detect,
                                                         mock_elevation):
        """Test config remains unchanged if discovery fails."""
        self.hass.config = Config()
        self.hass.config.config_dir = "/test/config"

        run_coroutine_threadsafe(
            config_util.async_process_ha_core_config(
                self.hass, {}), self.hass.loop
            ).result()

        blankConfig = Config()
        assert self.hass.config.latitude == blankConfig.latitude
        assert self.hass.config.longitude == blankConfig.longitude
        assert self.hass.config.elevation == blankConfig.elevation
        assert self.hass.config.location_name == blankConfig.location_name
        assert self.hass.config.units == blankConfig.units
        assert self.hass.config.time_zone == blankConfig.time_zone
        assert len(self.hass.config.whitelist_external_dirs) == 1
        assert "/test/config/www" in self.hass.config.whitelist_external_dirs

    @mock.patch('homeassistant.scripts.check_config.check_ha_config_file')
    def test_check_ha_config_file_correct(self, mock_check):
        """Check that restart propagates to stop."""
        mock_check.return_value = check_config.HomeAssistantConfig()
        assert run_coroutine_threadsafe(
            config_util.async_check_ha_config_file(self.hass),
            self.hass.loop
        ).result() is None

    @mock.patch('homeassistant.scripts.check_config.check_ha_config_file')
    def test_check_ha_config_file_wrong(self, mock_check):
        """Check that restart with a bad config doesn't propagate to stop."""
        mock_check.return_value = check_config.HomeAssistantConfig()
        mock_check.return_value.add_error("bad")

        assert run_coroutine_threadsafe(
            config_util.async_check_ha_config_file(self.hass),
            self.hass.loop
        ).result() == 'bad'


# pylint: disable=redefined-outer-name
@pytest.fixture
def merge_log_err(hass):
    """Patch _merge_log_error from packages."""
    with mock.patch('homeassistant.config._LOGGER.error') \
            as logerr:
        yield logerr


def test_merge(merge_log_err, hass):
    """Test if we can merge packages."""
    packages = {
        'pack_dict': {'input_boolean': {'ib1': None}},
        'pack_11': {'input_select': {'is1': None}},
        'pack_list': {'light': {'platform': 'test'}},
        'pack_list2': {'light': [{'platform': 'test'}]},
        'pack_none': {'wake_on_lan': None},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'input_boolean': {'ib2': None},
        'light': {'platform': 'test'}
    }
    config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 5
    assert len(config['input_boolean']) == 2
    assert len(config['input_select']) == 1
    assert len(config['light']) == 3
    assert isinstance(config['wake_on_lan'], OrderedDict)


def test_merge_try_falsy(merge_log_err, hass):
    """Ensure we dont add falsy items like empty OrderedDict() to list."""
    packages = {
        'pack_falsy_to_lst': {'automation': OrderedDict()},
        'pack_list2': {'light': OrderedDict()},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'automation': {'do': 'something'},
        'light': {'some': 'light'},
    }
    config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert len(config) == 3
    assert len(config['automation']) == 1
    assert len(config['light']) == 1


def test_merge_new(merge_log_err, hass):
    """Test adding new components to outer scope."""
    packages = {
        'pack_1': {'light': [{'platform': 'one'}]},
        'pack_11': {'input_select': {'ib1': None}},
        'pack_2': {
            'light': {'platform': 'one'},
            'panel_custom': {'pan1': None},
            'api': {}},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
    }
    config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 0
    assert 'api' in config
    assert len(config) == 5
    assert len(config['light']) == 2
    assert len(config['panel_custom']) == 1


def test_merge_type_mismatch(merge_log_err, hass):
    """Test if we have a type mismatch for packages."""
    packages = {
        'pack_1': {'input_boolean': [{'ib1': None}]},
        'pack_11': {'input_select': {'ib1': None}},
        'pack_2': {'light': {'ib1': None}},  # light gets merged - ensure_list
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'input_boolean': {'ib2': None},
        'input_select': [{'ib2': None}],
        'light': [{'platform': 'two'}]
    }
    config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 2
    assert len(config) == 4
    assert len(config['input_boolean']) == 1
    assert len(config['light']) == 2


def test_merge_once_only_keys(merge_log_err, hass):
    """Test if we have a merge for a comp that may occur only once. Keys."""
    packages = {'pack_2': {'api': None}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'api': None,
    }
    config_util.merge_packages_config(hass, config, packages)
    assert config['api'] == OrderedDict()

    packages = {'pack_2': {'api': {
        'key_3': 3,
    }}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'api': {
            'key_1': 1,
            'key_2': 2,
        }
    }
    config_util.merge_packages_config(hass, config, packages)
    assert config['api'] == {'key_1': 1, 'key_2': 2, 'key_3': 3, }

    # Duplicate keys error
    packages = {'pack_2': {'api': {
        'key': 2,
    }}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'api': {'key': 1, }
    }
    config_util.merge_packages_config(hass, config, packages)
    assert merge_log_err.call_count == 1


def test_merge_once_only_lists(hass):
    """Test if we have a merge for a comp that may occur only once. Lists."""
    packages = {'pack_2': {'api': {
        'list_1': ['item_2', 'item_3'],
        'list_2': ['item_1'],
        'list_3': [],
    }}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'api': {
            'list_1': ['item_1'],
        }
    }
    config_util.merge_packages_config(hass, config, packages)
    assert config['api'] == {
        'list_1': ['item_1', 'item_2', 'item_3'],
        'list_2': ['item_1'],
    }


def test_merge_once_only_dictionaries(hass):
    """Test if we have a merge for a comp that may occur only once. Dicts."""
    packages = {'pack_2': {'api': {
        'dict_1': {
            'key_2': 2,
            'dict_1.1': {'key_1.2': 1.2, },
        },
        'dict_2': {'key_1': 1, },
        'dict_3': {},
    }}}
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'api': {
            'dict_1': {
                'key_1': 1,
                'dict_1.1': {'key_1.1': 1.1, }
            },
        }
    }
    config_util.merge_packages_config(hass, config, packages)
    assert config['api'] == {
        'dict_1': {
            'key_1': 1,
            'key_2': 2,
            'dict_1.1': {'key_1.1': 1.1, 'key_1.2': 1.2, },
        },
        'dict_2': {'key_1': 1, },
    }


def test_merge_id_schema(hass):
    """Test if we identify the config schemas correctly."""
    types = {
        'panel_custom': 'list',
        'group': 'dict',
        'script': 'dict',
        'input_boolean': 'dict',
        'shell_command': 'dict',
        'qwikswitch': 'dict',
    }
    for name, expected_type in types.items():
        module = config_util.get_component(hass, name)
        typ, _ = config_util._identify_config_schema(module)
        assert typ == expected_type, "{} expected {}, got {}".format(
            name, expected_type, typ)


def test_merge_duplicate_keys(merge_log_err, hass):
    """Test if keys in dicts are duplicates."""
    packages = {
        'pack_1': {'input_select': {'ib1': None}},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
        'input_select': {'ib1': 1},
    }
    config_util.merge_packages_config(hass, config, packages)

    assert merge_log_err.call_count == 1
    assert len(config) == 2
    assert len(config['input_select']) == 1


@asyncio.coroutine
def test_merge_customize(hass):
    """Test loading core config onto hass object."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        'customize': {'a.a': {'friendly_name': 'A'}},
        'packages': {'pkg1': {'homeassistant': {'customize': {
            'b.b': {'friendly_name': 'BB'}}}}},
    }
    yield from config_util.async_process_ha_core_config(hass, core_config)

    assert hass.data[config_util.DATA_CUSTOMIZE].get('b.b') == \
        {'friendly_name': 'BB'}


async def test_auth_provider_config(hass):
    """Test loading auth provider config onto hass object."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        CONF_AUTH_PROVIDERS: [
            {'type': 'homeassistant'},
            {'type': 'legacy_api_password'},
        ],
        CONF_AUTH_MFA_MODULES: [
            {'type': 'totp'},
            {'type': 'totp', 'id': 'second'},
        ]
    }
    if hasattr(hass, 'auth'):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 2
    assert hass.auth.auth_providers[0].type == 'homeassistant'
    assert hass.auth.auth_providers[1].type == 'legacy_api_password'
    assert hass.auth.active is True
    assert len(hass.auth.auth_mfa_modules) == 2
    assert hass.auth.auth_mfa_modules[0].id == 'totp'
    assert hass.auth.auth_mfa_modules[1].id == 'second'


async def test_auth_provider_config_default(hass):
    """Test loading default auth provider config."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
    }
    if hasattr(hass, 'auth'):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config)

    assert len(hass.auth.auth_providers) == 1
    assert hass.auth.auth_providers[0].type == 'homeassistant'
    assert hass.auth.active is True
    assert len(hass.auth.auth_mfa_modules) == 1
    assert hass.auth.auth_mfa_modules[0].id == 'totp'


async def test_auth_provider_config_default_api_password(hass):
    """Test loading default auth provider config with api password."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
    }
    if hasattr(hass, 'auth'):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config, True)

    assert len(hass.auth.auth_providers) == 2
    assert hass.auth.auth_providers[0].type == 'homeassistant'
    assert hass.auth.auth_providers[1].type == 'legacy_api_password'
    assert hass.auth.active is True


async def test_auth_provider_config_default_trusted_networks(hass):
    """Test loading default auth provider config with trusted networks."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
    }
    if hasattr(hass, 'auth'):
        del hass.auth
    await config_util.async_process_ha_core_config(hass, core_config,
                                                   has_trusted_networks=True)

    assert len(hass.auth.auth_providers) == 2
    assert hass.auth.auth_providers[0].type == 'homeassistant'
    assert hass.auth.auth_providers[1].type == 'trusted_networks'
    assert hass.auth.active is True


async def test_disallowed_auth_provider_config(hass):
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        CONF_AUTH_PROVIDERS: [{
            'type': 'insecure_example',
            'users': [{
                'username': 'test-user',
                'password': 'test-pass',
                'name': 'Test Name'
            }],
        }]
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_provider_config(hass):
    """Test loading insecure example auth provider is disallowed."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        CONF_AUTH_PROVIDERS: [{
            'type': 'homeassistant',
        }, {
            'type': 'homeassistant',
        }]
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_auth_mfa_module_config(hass):
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        CONF_AUTH_MFA_MODULES: [{
            'type': 'insecure_example',
            'data': [{
                'user_id': 'mock-user',
                'pin': 'test-pin'
            }]
        }]
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


async def test_disallowed_duplicated_auth_mfa_module_config(hass):
    """Test loading insecure example auth mfa module is disallowed."""
    core_config = {
        'latitude': 60,
        'longitude': 50,
        'elevation': 25,
        'name': 'Huis',
        CONF_UNIT_SYSTEM: CONF_UNIT_SYSTEM_IMPERIAL,
        'time_zone': 'GMT',
        CONF_AUTH_MFA_MODULES: [{
            'type': 'totp',
        }, {
            'type': 'totp',
        }]
    }
    with pytest.raises(Invalid):
        await config_util.async_process_ha_core_config(hass, core_config)


def test_merge_split_component_definition(hass):
    """Test components with trailing description in packages are merged."""
    packages = {
        'pack_1': {'light one': {'l1': None}},
        'pack_2': {'light two': {'l2': None},
                   'light three': {'l3': None}},
    }
    config = {
        config_util.CONF_CORE: {config_util.CONF_PACKAGES: packages},
    }
    config_util.merge_packages_config(hass, config, packages)

    assert len(config) == 4
    assert len(config['light one']) == 1
    assert len(config['light two']) == 1
    assert len(config['light three']) == 1
