"""Test Home Assistant json utility functions."""
import os
import unittest
import sys
from tempfile import mkdtemp

from homeassistant.util.json import (SerializationError,
                                     load_json, save_json)
from homeassistant.exceptions import HomeAssistantError
import pytest

# Test data that can be saved as JSON
TEST_JSON_A = {"a": 1, "B": "two"}
TEST_JSON_B = {"a": "one", "B": 2}
# Test data that can not be saved as JSON (keys must be strings)
TEST_BAD_OBJECT = {("A",): 1}
# Test data that can not be loaded as JSON
TEST_BAD_SERIALIED = "THIS IS NOT JSON\n"


class TestJSON(unittest.TestCase):
    """Test util.json save and load."""

    def setUp(self):
        """Set up for tests."""
        self.tmp_dir = mkdtemp()

    def tearDown(self):
        """Clean up after tests."""
        for fname in os.listdir(self.tmp_dir):
            os.remove(os.path.join(self.tmp_dir, fname))
        os.rmdir(self.tmp_dir)

    def _path_for(self, leaf_name):
        return os.path.join(self.tmp_dir, leaf_name+".json")

    def test_save_and_load(self):
        """Test saving and loading back."""
        fname = self._path_for("test1")
        save_json(fname, TEST_JSON_A)
        data = load_json(fname)
        assert data == TEST_JSON_A

    # Skipped on Windows
    @unittest.skipIf(sys.platform.startswith('win'),
                     "private permissions not supported on Windows")
    def test_save_and_load_private(self):
        """Test we can load private files and that they are protected."""
        fname = self._path_for("test2")
        save_json(fname, TEST_JSON_A, private=True)
        data = load_json(fname)
        assert data == TEST_JSON_A
        stats = os.stat(fname)
        assert stats.st_mode & 0o77 == 0

    def test_overwrite_and_reload(self):
        """Test that we can overwrite an existing file and read back."""
        fname = self._path_for("test3")
        save_json(fname, TEST_JSON_A)
        save_json(fname, TEST_JSON_B)
        data = load_json(fname)
        assert data == TEST_JSON_B

    def test_save_bad_data(self):
        """Test error from trying to save unserialisable data."""
        fname = self._path_for("test4")
        with pytest.raises(SerializationError):
            save_json(fname, TEST_BAD_OBJECT)

    def test_load_bad_data(self):
        """Test error from trying to load unserialisable data."""
        fname = self._path_for("test5")
        with open(fname, "w") as fh:
            fh.write(TEST_BAD_SERIALIED)
        with pytest.raises(HomeAssistantError):
            load_json(fname)
