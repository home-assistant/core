"""Test check_config script."""
import unittest
import logging
import os

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


def tearDownModule(self):  # pylint: disable=invalid-name
    """Clean files."""
    # .HA_VERSION created during bootstrap's config update
    path = get_test_config_dir('.HA_VERSION')
    if os.path.isfile(path):
        os.remove(path)


class TestCheckConfig(unittest.TestCase):
    """Tests for the homeassistant.scripts.check_config module."""

    # pylint: disable=no-self-use,invalid-name
    def test_config_platform_valid(self):
        """Test a valid platform setup."""
        files = {
            'light.yaml': BASE_CONFIG + 'light:\n  platform: hue',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('light.yaml'))
            self.assertDictEqual({
                'components': {'light': [{'platform': 'hue'}]},
                'except': {},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': {}
            }, res)

    def test_config_component_platform_fail_validation(self):
        """Test errors if component & platform not found."""
        files = {
            'component.yaml': BASE_CONFIG + 'http:\n  password: err123',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('component.yaml'))
            self.assertDictEqual({
                'components': {},
                'except': {'http': {'password': 'err123'}},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': {}
            }, res)

        files = {
            'platform.yaml': (BASE_CONFIG + 'mqtt:\n\n'
                              'light:\n  platform: mqtt_json'),
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('platform.yaml'))
            self.assertDictEqual({
                'components': {'mqtt': {'keepalive': 60, 'port': 1883,
                                        'protocol': '3.1.1'}},
                'except': {'light.mqtt_json': {'platform': 'mqtt_json'}},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': {}
            }, res)

    def test_component_platform_not_found(self):
        """Test errors if component or platform not found."""
        files = {
            'badcomponent.yaml': BASE_CONFIG + 'beer:',
            'badplatform.yaml': BASE_CONFIG + 'light:\n  platform: beer',
        }
        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('badcomponent.yaml'))
            self.assertDictEqual({
                'components': {},
                'except': {check_config.ERROR_STR:
                           ['Component not found: beer']},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': {}
            }, res)

            res = check_config.check(get_test_config_dir('badplatform.yaml'))
            self.assertDictEqual({
                'components': {},
                'except': {check_config.ERROR_STR:
                           ['Platform not found: light.beer']},
                'secret_cache': {},
                'secrets': {},
                'yaml_files': {}
            }, res)

    def test_secrets(self):
        """Test secrets config checking method."""
        files = {
            'secret.yaml': (BASE_CONFIG +
                            'http:\n'
                            '  api_password: !secret http_pw'),
            'secrets.yaml': ('logger: debug\n'
                             'http_pw: abc123'),
        }

        with patch_yaml_files(files):
            res = check_config.check(get_test_config_dir('secret.yaml'))
            self.assertDictEqual({
                'components': {'http': {'api_password': 'abc123',
                                        'server_port': 8123}},
                'except': {},
                'secret_cache': {},
                'secrets': {'http_pw': 'abc123'},
                'yaml_files': {'secrets.yaml': True}
            }, res)
