"""The tests for the denonavr media player platform."""
import unittest
from unittest import mock

from homeassistant.components.denonavr import media_player as denonavr


class TestDenonDevice(unittest.TestCase):
    """Test the DenonDevice class."""

    def setUp(self):
        """Configure a fake device for each test."""
        self.device = denonavr.DenonDevice(mock.MagicMock())

    def test_get_command(self):
        """Test generic command functionality."""
        self.device.get_command("/goform/formiPhoneAppDirect.xml?RCKSK0410370")
