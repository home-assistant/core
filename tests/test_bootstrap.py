"""
tests.test_bootstrap
~~~~~~~~~~~~~~~~~~~~

Tests bootstrap.
"""
# pylint: disable=too-many-public-methods,protected-access
import os
import tempfile
import unittest

from homeassistant import bootstrap
from homeassistant.const import (__version__, CONF_LATITUDE, CONF_LONGITUDE,
                                 CONF_NAME, CONF_CUSTOMIZE)
import homeassistant.util.dt as dt_util
from homeassistant.helpers.entity import Entity

from tests.common import get_test_home_assistant


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

            hass = get_test_home_assistant()
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

            hass = get_test_home_assistant()
            hass.config.config_dir = config_dir

            bootstrap.process_ha_config_upgrade(hass)

            self.assertTrue(os.path.isfile(check_file))

    def test_entity_customization(self):
        """ Test entity customization through config """
        config = {CONF_LATITUDE: 50,
                  CONF_LONGITUDE: 50,
                  CONF_NAME: 'Test',
                  CONF_CUSTOMIZE: {'test.test': {'hidden': True}}}

        hass = get_test_home_assistant()

        bootstrap.process_ha_core_config(hass, config)

        entity = Entity()
        entity.entity_id = 'test.test'
        entity.hass = hass
        entity.update_ha_state()

        state = hass.states.get('test.test')

        self.assertTrue(state.attributes['hidden'])
