"""Test check_config script."""
import asyncio
import logging
import os  # noqa: F401 pylint: disable=unused-import
import unittest
from unittest.mock import patch

import homeassistant.scripts.check_config as check_config
from homeassistant.config import YAML_CONFIG_FILE
from tests.common import patch_yaml_files, get_test_config_dir

_LOGGER = logging.getLogger(__name__)

BASE_CONFIG = (
    'homeassistant:\n'
    '  name: Home\n'
    '  latitude: -26.107361\n'
    '  longitude: 28.054500\n'
    '  elevation: 1600\n'
    '  unit_system: metric\n'
    '  time_zone: GMT\n'
    '\n\n'
)

BAD_CORE_CONFIG = (
    'homeassistant:\n'
    '  unit_system: bad\n'
    '\n\n'
)


def normalize_yaml_files(check_dict):
    """Remove configuration path from ['yaml_files']."""
    root = get_test_config_dir()
    return [key.replace(root, '...')
            for key in sorted(check_dict['yaml_files'].keys())]


# pylint: disable=unsubscriptable-object
class TestCheckConfig(unittest.TestCase):
    """Tests for the homeassistant.scripts.check_config module."""

    def setUp(self):
        """Prepare the test."""
        # Somewhere in the tests our event loop gets killed,
        # this ensures we have one.
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())

        # Will allow seeing full diff
        self.maxDiff = None  # pylint: disable=invalid-name

    # pylint: disable=no-self-use,invalid-name
    @patch('os.path.isfile', return_value=True)
    def test_bad_core_config(self, isfile_patch):
        """Test a bad core config setup."""
        files = {
            YAML_CONFIG_FILE: BAD_CORE_CONFIG,
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir())
            assert res['except'].keys() == {'homeassistant'}
            assert res['except']['homeassistant'][1] == {'unit_system': 'bad'}

    @patch('os.path.isfile', return_value=True)
    def test_config_platform_valid(self, isfile_patch):
        """Test a valid platform setup."""
        files = {
            YAML_CONFIG_FILE: BASE_CONFIG + 'light:\n  platform: demo',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir())
            assert res['components'].keys() == {'homeassistant', 'light'}
            assert res['components']['light'] == [{'platform': 'demo'}]
            assert res['except'] == {}
            assert res['secret_cache'] == {}
            assert res['secrets'] == {}
            assert len(res['yaml_files']) == 1

    @patch('os.path.isfile', return_value=True)
    def test_component_platform_not_found(self, isfile_patch):
        """Test errors if component or platform not found."""
        # Make sure they don't exist
        files = {
            YAML_CONFIG_FILE: BASE_CONFIG + 'beer:',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir())
            assert res['components'].keys() == {'homeassistant'}
            assert res['except'] == {
                check_config.ERROR_STR: ['Component not found: beer']}
            assert res['secret_cache'] == {}
            assert res['secrets'] == {}
            assert len(res['yaml_files']) == 1

        files = {
            YAML_CONFIG_FILE: BASE_CONFIG + 'light:\n  platform: beer',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir())
            assert res['components'].keys() == {'homeassistant', 'light'}
            assert res['components']['light'] == []
            assert res['except'] == {
                check_config.ERROR_STR: [
                    'Platform not found: light.beer',
                ]}
            assert res['secret_cache'] == {}
            assert res['secrets'] == {}
            assert len(res['yaml_files']) == 1

    @patch('os.path.isfile', return_value=True)
    def test_secrets(self, isfile_patch):
        """Test secrets config checking method."""
        secrets_path = get_test_config_dir('secrets.yaml')

        files = {
            get_test_config_dir(YAML_CONFIG_FILE): BASE_CONFIG + (
                'http:\n'
                '  api_password: !secret http_pw'),
            secrets_path: (
                'logger: debug\n'
                'http_pw: abc123'),
        }

        with patch_yaml_files(files):

            res = check_config.check(get_test_config_dir(), True)

            assert res['except'] == {}
            assert res['components'].keys() == {'homeassistant', 'http'}
            assert res['components']['http'] == {
                'api_password': 'abc123',
                'cors_allowed_origins': [],
                'ip_ban_enabled': True,
                'login_attempts_threshold': -1,
                'server_host': '0.0.0.0',
                'server_port': 8123,
                'trusted_networks': [],
                'ssl_profile': 'modern',
            }
            assert res['secret_cache'] == {secrets_path: {'http_pw': 'abc123'}}
            assert res['secrets'] == {'http_pw': 'abc123'}
            assert normalize_yaml_files(res) == [
                '.../configuration.yaml', '.../secrets.yaml']

    @patch('os.path.isfile', return_value=True)
    def test_package_invalid(self, isfile_patch):
        """Test a valid platform setup."""
        files = {
            YAML_CONFIG_FILE: BASE_CONFIG + (
                '  packages:\n'
                '    p1:\n'
                '      group: ["a"]'),
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir())

            assert res['except'].keys() == {'homeassistant.packages.p1.group'}
            assert res['except']['homeassistant.packages.p1.group'][1] == \
                {'group': ['a']}
            assert len(res['except']) == 1
            assert res['components'].keys() == {'homeassistant'}
            assert len(res['components']) == 1
            assert res['secret_cache'] == {}
            assert res['secrets'] == {}
            assert len(res['yaml_files']) == 1

    def test_bootstrap_error(self):
        """Test a valid platform setup."""
        files = {
            YAML_CONFIG_FILE: BASE_CONFIG + 'automation: !include no.yaml',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir(YAML_CONFIG_FILE))
            err = res['except'].pop(check_config.ERROR_STR)
            assert len(err) == 1
            assert res['except'] == {}
            assert res['components'] == {}  # No components, load failed
            assert res['secret_cache'] == {}
            assert res['secrets'] == {}
            assert res['yaml_files'] == {}
