"""NuHeat component tests."""
import unittest

from unittest.mock import patch
from tests.common import get_test_home_assistant, MockDependency

from homeassistant.components import nuheat

VALID_CONFIG = {
    "nuheat": {
        "username": "warm",
        "password": "feet",
        "devices": "thermostat123"
    }
}


class TestNuHeat(unittest.TestCase):
    """Test the NuHeat component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Initialize the values for this test class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Teardown this test class. Stop hass."""
        self.hass.stop()

    @MockDependency("nuheat")
    @patch("homeassistant.helpers.discovery.load_platform")
    def test_setup(self, mocked_nuheat, mocked_load):
        """Test setting up the NuHeat component."""
        nuheat.setup(self.hass, self.config)

        mocked_nuheat.NuHeat.assert_called_with("warm", "feet")
        self.assertIn(nuheat.DOMAIN, self.hass.data)
        self.assertEqual(2, len(self.hass.data[nuheat.DOMAIN]))
        self.assertIsInstance(
            self.hass.data[nuheat.DOMAIN][0], type(mocked_nuheat.NuHeat())
        )
        self.assertEqual(self.hass.data[nuheat.DOMAIN][1], "thermostat123")

        mocked_load.assert_called_with(
            self.hass, "climate", nuheat.DOMAIN, {}, self.config
        )
