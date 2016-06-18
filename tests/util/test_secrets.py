"""Test config utils."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import os

import homeassistant.config as config_util
import homeassistant.util.secrets as secrets

from tests.common import get_test_config_dir
CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)


def load_yaml(string):
    """Write a string to file and load."""
    with open(YAML_PATH, 'w') as file:
        file.write(string)
    return config_util.load_yaml_config_file(YAML_PATH)


class TestSecrets(unittest.TestCase):
    """Test the secrets utility."""

    def setUp(self):  # pylint: disable=invalid-name
        """Create & load secrets file."""
        load_yaml('http_pw: pwhttp\n'
                  'comp1_un: un1\n'
                  'comp1_pw: pw1\n'
                  'stale_pw: not_used')
        secrets.load_secrets_yaml(YAML_PATH, os.path.basename(YAML_PATH))
        self._yaml = load_yaml('http:\n'
                               '  api_password: !secret http_pw\n'
                               'component:\n'
                               '  username: !secret comp1_un\n'
                               '  password: !secret comp1_pw\n'
                               '')

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up."""
        for path in [YAML_PATH]:
            if os.path.isfile(path):
                os.remove(path)

    def test_secrets_parsed_correctly(self):
        """Did secrets load ok."""
        expected = {'api_password': 'pwhttp'}
        self.assertEqual(expected, self._yaml['http'])

        expected = {
            'username': 'un1',
            'password': 'pw1'}
        self.assertEqual(expected, self._yaml['component'])

    def test_x_missing_secrets(self):
        """Test missing."""
        missing = secrets.check_secrets(False)['missing']
        self.assertEqual(missing, [])

        secrets.get_secret('missing_secret', False)
        missing = secrets.check_secrets(False)['missing']
        expected = ['missing_secret']
        self.assertEqual(expected, missing)

    def test_x_unused_secrets(self):
        """Test unused."""
        unused = secrets.check_secrets(False)['unused']
        expected = ['stale_pw']
        self.assertEqual(expected, unused)
