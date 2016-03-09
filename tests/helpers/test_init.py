"""Test component helpers."""
# pylint: disable=protected-access,too-many-public-methods
import unittest

from homeassistant import helpers

from tests.common import get_test_home_assistant


class TestHelpers(unittest.TestCase):
    """Tests homeassistant.helpers module."""

    def setUp(self):  # pylint: disable=invalid-name
        """Init needed objects."""
        self.hass = get_test_home_assistant()

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that was started."""
        self.hass.stop()

    def test_extract_domain_configs(self):
        """Test the extraction of domain configuration."""
        config = {
            'zone': None,
            'zoner': None,
            'zone ': None,
            'zone Hallo': None,
            'zone 100': None,
        }

        self.assertEqual(set(['zone', 'zone Hallo', 'zone 100']),
                         set(helpers.extract_domain_configs(config, 'zone')))
