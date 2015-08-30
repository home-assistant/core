"""
tests.test_bootstrap
~~~~~~~~~~~~~~~~~~~~

Tests bootstrap.
"""
# pylint: disable=too-many-public-methods,protected-access
import tempfile
import unittest
from unittest import mock

from homeassistant import bootstrap
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
