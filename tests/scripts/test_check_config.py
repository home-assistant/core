"""Test check_config script."""
import asyncio
import logging
import os
import unittest
from unittest.mock import patch

import homeassistant.scripts.check_config as check_config
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


def change_yaml_files(check_dict):
    """Change the ['yaml_files'] property and remove the config path.

    Also removes other files like service.yaml that gets loaded
    """
    root = get_test_config_dir()
    keys = check_dict['yaml_files'].keys()
    check_dict['yaml_files'] = []
    for key in sorted(keys):
        if not key.startswith('/'):
            check_dict['yaml_files'].append(key)
        if key.startswith(root):
            check_dict['yaml_files'].append('...' + key[len(root):])


def tearDownModule(self):  # pylint: disable=invalid-name
    """Clean files."""
    # .HA_VERSION created during bootstrap's config update
    path = get_test_config_dir('.HA_VERSION')
    if os.path.isfile(path):
        os.remove(path)


@patch('asyncio.get_event_loop', return_value=asyncio.new_event_loop())
class TestCheckConfig(unittest.TestCase):
    """Tests for the homeassistant.scripts.check_config module."""

    # pylint: disable=no-self-use,invalid-name
    def test_config_platform_valid(self, mock_get_loop):
        """Test a valid platform setup."""
        files = {
            'light.yaml': BASE_CONFIG + 'light:\n  platform: demo',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('light.yaml'))
            change_yaml_files(res)
            self.assertDictEqual({
                'components': {'light': [{'platform': 'demo'}]},
                'except': {},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': ['.../light.yaml']
            }, res)

    def test_config_component_platform_fail_validation(self, mock_get_loop):
        """Test errors if component & platform not found."""
        files = {
            'component.yaml': BASE_CONFIG + 'http:\n  password: err123',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('component.yaml'))
            change_yaml_files(res)
            self.assertDictEqual({
                'components': {},
                'except': {'http': {'password': 'err123'}},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': ['.../component.yaml']
            }, res)

        files = {
            'platform.yaml': (BASE_CONFIG + 'mqtt:\n\n'
                              'light:\n  platform: mqtt_json'),
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('platform.yaml'))
            change_yaml_files(res)
            self.assertDictEqual({
                'components': {'mqtt': {'keepalive': 60, 'port': 1883,
                                        'protocol': '3.1.1'}},
                'except': {'light.mqtt_json': {'platform': 'mqtt_json'}},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': ['.../platform.yaml']
            }, res)

    def test_component_platform_not_found(self, mock_get_loop):
        """Test errors if component or platform not found."""
        files = {
            'badcomponent.yaml': BASE_CONFIG + 'beer:',
            'badplatform.yaml': BASE_CONFIG + 'light:\n  platform: beer',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('badcomponent.yaml'))
            change_yaml_files(res)
            self.assertDictEqual({
                'components': {},
                'except': {check_config.ERROR_STR:
                           ['Component not found: beer']},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': ['.../badcomponent.yaml']
            }, res)

            res = check_config.check(get_test_config_dir('badplatform.yaml'))
            change_yaml_files(res)
            self.assertDictEqual({
                'components': {},
                'except': {check_config.ERROR_STR:
                           ['Platform not found: light.beer']},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': ['.../badplatform.yaml']
            }, res)

    def test_secrets(self, mock_get_loop):
        """Test secrets config checking method."""
        files = {
            get_test_config_dir('secret.yaml'): (
                BASE_CONFIG +
                'http:\n'
                '  api_password: !secret http_pw'),
            'secrets.yaml': ('logger: debug\n'
                             'http_pw: abc123'),
        }
        self.maxDiff = None

        with patch_yaml_files(files):
            config_path = get_test_config_dir('secret.yaml')
            secrets_path = get_test_config_dir('secrets.yaml')

            res = check_config.check(config_path)
            change_yaml_files(res)

            # convert secrets OrderedDict to dict for assertequal
            for key, val in res['secret_cache'].items():
                res['secret_cache'][key] = dict(val)

            self.assertDictEqual({
                'components': {'http': {'api_password': 'abc123',
                                        'server_port': 8123}},
                'except': {},
                'secret_cache': {secrets_path: {'http_pw': 'abc123'}},
                'secrets': {'http_pw': 'abc123'},
                'yaml_files': ['.../secret.yaml', '.../secrets.yaml']
            }, res)
