"""The tests for the denonavr media player platform."""
import unittest
from unittest import mock

from homeassistant.components.denonavr import media_player as denonavr


class FakeDenonDevice(denonavr.DenonDevice):
    """A fake device without the client setup required for the real one."""

    def __init__(self, *args, **kwargs):
        """Initialise parameters needed for tests with fake values."""
        self._receiver = mock.MagicMock()
        self._name = "fake_device"


class TestDenonDevice(unittest.TestCase):
    """Test the LgWebOSDevice class."""

    def setUp(self):
        """Configure a fake device for each test."""
        self.device = FakeDenonDevice()

    def test_get_command(self):
        """Test generic command functionality."""
        self.device.get_command("/goform/formiPhoneAppDirect.xml?RCKSK0410370")
