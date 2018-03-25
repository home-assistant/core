"""The test for the Melissa Climate component."""
import unittest
from tests.common import get_test_home_assistant, MockDependency

from homeassistant.components import melissa

VALID_CONFIG = {
    "melissa": {
        "username": "********",
        "password": "********",
    }
}


class TestMelissa(unittest.TestCase):
    """Test the Melissa component."""

    def setUp(self):  # pylint: disable=invalid-name
        """Initialize the values for this test class."""
        self.hass = get_test_home_assistant()
        self.config = VALID_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Teardown this test class. Stop hass."""
        self.hass.stop()

    @MockDependency("melissa")
    def test_setup(self, mocked_melissa):
        """Test setting up the Melissa component."""
        melissa.setup(self.hass, self.config)

        mocked_melissa.Melissa.assert_called_with(
            username="********", password="********")
        self.assertIn(melissa.DATA_MELISSA, self.hass.data)
        self.assertIsInstance(
            self.hass.data[melissa.DATA_MELISSA], type(
                mocked_melissa.Melissa())
        )
