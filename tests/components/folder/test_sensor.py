"""The tests for the folder sensor."""
import os
import unittest

from homeassistant.components.folder.sensor import CONF_FOLDER_PATHS
from homeassistant.setup import setup_component

from tests.common import get_test_home_assistant

CWD = os.path.join(os.path.dirname(__file__))
TEST_FOLDER = "test_folder"
TEST_DIR = os.path.join(CWD, TEST_FOLDER)
TEST_TXT = "mock_test_folder.txt"
TEST_FILE = os.path.join(TEST_DIR, TEST_TXT)


def create_file(path):
    """Create a test file."""
    with open(path, "w") as test_file:
        test_file.write("test")


class TestFolderSensor(unittest.TestCase):
    """Test the filesize sensor."""

    def setup_method(self, method):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        if not os.path.isdir(TEST_DIR):
            os.mkdir(TEST_DIR)
        self.hass.config.whitelist_external_dirs = {TEST_DIR}

    def teardown_method(self, method):
        """Stop everything that was started."""
        if os.path.isfile(TEST_FILE):
            os.remove(TEST_FILE)
            os.rmdir(TEST_DIR)
        self.hass.stop()

    def test_invalid_path(self):
        """Test that an invalid path is caught."""
        config = {"sensor": {"platform": "folder", CONF_FOLDER_PATHS: "invalid_path"}}
        assert setup_component(self.hass, "sensor", config)
        assert len(self.hass.states.entity_ids()) == 0

    def test_valid_path(self):
        """Test for a valid path."""
        create_file(TEST_FILE)
        config = {"sensor": {"platform": "folder", CONF_FOLDER_PATHS: TEST_DIR}}
        assert setup_component(self.hass, "sensor", config)
        assert len(self.hass.states.entity_ids()) == 1
        state = self.hass.states.get("sensor.test_folder")
        assert state.state == "0.0"
        assert state.attributes.get("number_of_files") == 1
