"""Test config utils."""
# pylint: disable=too-many-public-methods,protected-access
import unittest
import os
import collections
import logging

import homeassistant.config as config_util
import homeassistant.util.secrets as secrets

from tests.common import get_test_config_dir
CONFIG_DIR = get_test_config_dir()
YAML_PATH = os.path.join(CONFIG_DIR, config_util.YAML_CONFIG_FILE)
# YAML_PATH = "/home/pi/test_conf.yaml"


def ordered_dict(cdict):
    """Recursively convert dict to OrderedDict."""
    if isinstance(cdict, dict):
        odict = collections.OrderedDict(cdict)
        for key, value in odict.items():
            odict[key] = ordered_dict(value)
        return odict
    elif isinstance(cdict, list):
        # pylint: disable=consider-using-enumerate
        for idx in range(len(cdict)):
            cdict[idx] = ordered_dict(cdict[idx])
        return cdict
    else:
        return cdict


def load_yaml(string):
    """Write a string to file and load."""
    with open(YAML_PATH, 'w') as file:
        file.write(string)
    return config_util.load_yaml_config_file(YAML_PATH)


class TestSecrets(unittest.TestCase):
    """Test the secrets utility."""

    def setUp(self):  # pylint: disable=invalid-name
        """Create & load secrets file."""
        load_yaml('/password: pw1\n'
                  '/section/secret: pw2\n'
                  '/section_2/password: pw3\n'
                  '/section/b: the_b\n'
                  '/stale/and/placeholder/: ' + secrets.SECRET_PLACEHOLDER)
        secrets.load_secrets_config_file(YAML_PATH,
                                         os.path.basename(YAML_PATH))
        # To enable logging for secrets module, uncomment the next line:
        # secrets.logging.disable(logging.NOTSET)

    def tearDown(self):  # pylint: disable=invalid-name
        """Clean up."""
        for path in [YAML_PATH]:
            if os.path.isfile(path):
                os.remove(path)

    def test_secrets_prepared_ok(self):
        """Did secrets load ok."""
        self.assertEqual(len(secrets.SECRET_DICT), 5)

    def test_secret_placeholder_parsing(self):
        """Make sure the placeholder was parsed correctly in secrets."""
        self.assertEqual(secrets.SECRET_DICT['/stale/and/placeholder/'],
                         secrets.SECRET_PLACEHOLDER)

    def test_ordered_dict(self):
        """Test order_dict method."""
        as_string = load_yaml('section:\n'
                              '  items:\n'
                              '    - item1: one\n'
                              '    - item2:\n'
                              '        two: 2')
        as_dict = ordered_dict({
            'section': {
                'items': [{'item1': 'one'},
                          {'item2': {'two': 2}}],
            }})
        self.assertEqual(as_dict, as_string)

    def test_add_password(self):
        """Add password on username."""
        decoded = secrets.decode(ordered_dict({
            'username': 'un1'}))
        expected = {
            'username': 'un1',
            'password': 'pw1'}
        self.assertEqual(expected, decoded)

    def test_preserve_existing_password(self):
        """Don't overwrite existing password."""
        decoded = secrets.decode(ordered_dict({
            'username': 'un1',
            'password': 'pw**'}))
        expected = {
            'username': 'un1',
            'password': 'pw**'}
        self.assertEqual(expected, decoded)

    def test_add_password_placeholder(self):
        """Dont overwrite existing password."""
        decoded = secrets.decode(ordered_dict({
            'username': 'un1',
            'password': secrets.SECRET_PLACEHOLDER}))
        expected = {
            'username': 'un1',
            'password': 'pw1'}
        self.assertEqual(expected, decoded)

    def test_other_secret_placeholder(self):
        """Secret placeholder."""
        decoded = secrets.decode(ordered_dict({
            'section': {
                'secret': secrets.SECRET_PLACEHOLDER}}))
        expected = {'section': {'secret': 'pw2'}}
        self.assertEqual(expected, decoded)

    def test_placeholder_in_section(self):
        """Secret placeholder."""
        decoded = secrets.decode(ordered_dict({
            'section 2': {
                'password': secrets.SECRET_PLACEHOLDER}}))
        expected = {'section 2': {'password': 'pw3'}}
        self.assertEqual(expected, decoded)

    def test_in_list(self):
        """Item in list."""
        decoded = secrets.decode(ordered_dict({
            'section': [{'a': 'a'}, {'b': secrets.SECRET_PLACEHOLDER}]}))
        expected = {'section': [{'a': 'a'}, {'b': 'the_b'}]}
        self.assertEqual(expected, decoded)

    def test_z_stale_sectrets(self):
        """Test stale."""
        stale = secrets.check_stale_secrets(False)
        expected = ['/stale/and/placeholder/']
        self.assertEqual(expected, stale)
