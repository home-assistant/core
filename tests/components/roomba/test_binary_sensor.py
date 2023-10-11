"""Test to test the module binary_sensor.py."""
import unittest
from unittest.mock import Mock, patch

from homeassistant.components.roomba.binary_sensor import get_bin_status


class TestGetBinStatus(unittest.TestCase):
    """Test case for the 'get_bin_status' method in the binary_sensor module."""

    @patch("homeassistant.components.roomba.binary_sensor.roomba_reported_state")
    def test_get_bin_status_returns_bin_status(self, mock_roomba_reported_state):
        """Test the behavior of a function with a mocked dependency."""

        # Mock the roomba_reported_state function
        mock_roomba_reported_state.return_value = {"bin": {"status": "full"}}

        # Call the get_bin_status method
        bin_status = get_bin_status(Mock())

        # Ensure that the bin_status matches the expected value
        self.assertEqual(bin_status, {"status": "full"})


if __name__ == "__main__":
    unittest.main()
