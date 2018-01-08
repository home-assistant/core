"""The test for the Melissa Climate component."""
import unittest

from unittest.mock import patch
from tests.common import get_test_home_assistant, MockDependency

from homeassistant.components import melissa

VALID_CONFIG = {
    "melissa": {
        "username": "warm",
        "password": "feet",
    }
}


class TestNuHeat(unittest.TestCase):
    """Test the Melissa component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Initialize the values for this test class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Teardown this test class. Stop hass."""
        self.hass.stop()

    @MockDependency("melissa")
    @patch("homeassistant.helpers.discovery.load_platform")
    def test_setup(self, mocked_melissa, mocked_load):
        """Test setting up the Melissa component."""
        melissa.setup(self.hass, self.config)

        mocked_melissa.Melissa.assert_called_with(
            username="warm", password="feet")
        self.assertIn(melissa.DATA_MELISSA, self.hass.data)
        self.assertIsInstance(
            self.hass.data[melissa.DATA_MELISSA], type(
                mocked_melissa.Melissa())
        )
