"""The tests for the filesize sensor."""
import os
import unittest

from homeassistant.components.filesize.sensor import CONF_FILE_PATHS
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

TEST_DIR = os.path.join(os.path.dirname(__file__))
TEST_FILE = os.path.join(TEST_DIR, "mock_file_test_filesize.txt")


def create_file(path):
    """Create a test file."""
    with open(path, "w") as test_file:
        test_file.write("test")


class TestFileSensor(unittest.TestCase):
    """Test the filesize sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        self.hass.config.whitelist_external_dirs = {TEST_DIR}

    def teardown_method(self, method):
        """Stop everything that was started."""
        if os.path.isfile(TEST_FILE):
            os.remove(TEST_FILE)
        self.hass.stop()

    def test_invalid_path(self):
        """Test that an invalid path is caught."""
        config = {"sensor": {"platform": "filesize", CONF_FILE_PATHS: ["invalid_path"]}}
        assert setup_component(self.hass, "sensor", config)
        assert len(self.hass.states.entity_ids()) == 0

    def test_valid_path(self):
        """Test for a valid path."""
        create_file(TEST_FILE)
        config = {"sensor": {"platform": "filesize", CONF_FILE_PATHS: [TEST_FILE]}}
        assert setup_component(self.hass, "sensor", config)
        self.hass.block_till_done()
        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get("sensor.mock_file_test_filesize_txt")
        assert state.state == "0.0"
        assert state.attributes.get("bytes") == 4
