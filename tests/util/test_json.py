"""Test Home Assistant json utility functions."""
from datetime import datetime
from functools import partial
from json import JSONEncoder, dumps
import math
import os
from tempfile import mkdtemp
from unittest.mock import Mock, patch

import pytest

from homeassistant.core import Event, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.json import JSONEncoder as DefaultHASSJSONEncoder
from homeassistant.util.json import (
    SerializationError,
    find_paths_unserializable_data,
    load_json,
    save_json,
)

# Test data that can be saved as JSON
TEST_JSON_A = {"a": 1, "B": "two"}
TEST_JSON_B = {"a": "one", "B": 2}
# Test data that can not be loaded as JSON
TEST_BAD_SERIALIED = "THIS IS NOT JSON\n"
TMP_DIR = None


@pytest.fixture(autouse=True)
def setup_and_teardown():
    """Clean up after tests."""
    global TMP_DIR
    TMP_DIR = mkdtemp()

    yield

    for fname in os.listdir(TMP_DIR):
        os.remove(os.path.join(TMP_DIR, fname))
    os.rmdir(TMP_DIR)


def _path_for(leaf_name):
    return os.path.join(TMP_DIR, f"{leaf_name}.json")


def test_save_and_load_private():
    """Test we can load private files and that they are protected."""
    fname = _path_for("test2")
    save_json(fname, TEST_JSON_A, private=True)
    data = load_json(fname)
    assert data == TEST_JSON_A
    stats = os.stat(fname)
    assert stats.st_mode & 0o77 == 0



def test_load_bad_data():
    """Test error from trying to load unserialisable data."""
    fname = _path_for("test5")
    with open(fname, "w") as fh:
        fh.write(TEST_BAD_SERIALIED)
    with pytest.raises(HomeAssistantError):
        load_json(fname)


def test_ValueErrorException():
    try:
        fname = _path_for("test1")
        save_json(fname, {1: "a", 2: "b"})
        load_json('')
    except HomeAssistantError:
        pass