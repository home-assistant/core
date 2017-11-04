"""The tests for the pan_tilt_phat component."""
import unittest

from tests.common import get_test_home_assistant


class TestPanTiltPhat(unittest.TestCase):
    """Test the panel_custom component."""

    def setup(self):
        """Setup things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()
