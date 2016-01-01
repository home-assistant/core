"""
tests.test_bootstrap
~~~~~~~~~~~~~~~~~~~~

Tests bootstrap.
"""
# pylint: disable=too-many-public-methods,protected-access
import os
import tempfile
import unittest
from unittest import mock

from homeassistant import core, bootstrap
from homeassistant.const import __version__
import homeassistant.util.dt as dt_util

from tests.common import mock_detect_location_info


class TestBootstrap(unittest.TestCase):
    """ Test the bootstrap utils. """

    def setUp(self):
        self.orig_timezone = dt_util.DEFAULT_TIME_ZONE

    def tearDown(self):
        dt_util.DEFAULT_TIME_ZONE = self.orig_timezone

    def test_from_config_file(self):
        components = ['browser', 'conversation', 'script']
        with tempfile.NamedTemporaryFile() as fp:
            for comp in components:
                fp.write('{}:\n'.format(comp).encode('utf-8'))
            fp.flush()

            with mock.patch('homeassistant.util.location.detect_location_info',
                            mock_detect_location_info):
                hass = bootstrap.from_config_file(fp.name)

            components.append('group')

            self.assertEqual(sorted(components),
                             sorted(hass.config.components))

    def test_remove_lib_on_upgrade(self):
        with tempfile.TemporaryDirectory() as config_dir:
            version_path = os.path.join(config_dir, '.HA_VERSION')
            lib_dir = os.path.join(config_dir, 'lib')
            check_file = os.path.join(lib_dir, 'check')

            with open(version_path, 'wt') as outp:
                outp.write('0.7.0')

            os.mkdir(lib_dir)

            with open(check_file, 'w'):
                pass

            hass = core.HomeAssistant()
            hass.config.config_dir = config_dir

            self.assertTrue(os.path.isfile(check_file))
            bootstrap.process_ha_config_upgrade(hass)
            self.assertFalse(os.path.isfile(check_file))

    def test_not_remove_lib_if_not_upgrade(self):
        with tempfile.TemporaryDirectory() as config_dir:
            version_path = os.path.join(config_dir, '.HA_VERSION')
            lib_dir = os.path.join(config_dir, 'lib')
            check_file = os.path.join(lib_dir, 'check')

            with open(version_path, 'wt') as outp:
                outp.write(__version__)

            os.mkdir(lib_dir)

            with open(check_file, 'w'):
                pass

            hass = core.HomeAssistant()
            hass.config.config_dir = config_dir

            bootstrap.process_ha_config_upgrade(hass)

            self.assertTrue(os.path.isfile(check_file))
