"""Test Home Assistant json utility functions."""
from datetime import datetime
from functools import partial
from json import JSONEncoder, dumps
import math
import os
import string
import sys
from tempfile import mkdtemp
import unittest

import pytest

from homeassistant.core import Event, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util.json import (
    SerializationError,
    find_paths_unserializable_data,
    load_json,
    save_json,
)

from tests.async_mock import Mock

# Test data that can be saved as JSON
TEST_JSON_A = {"a": 1, "B": "two"}
TEST_JSON_B = {"a": "one", "B": 2}
# Test data that can not be loaded as JSON
TEST_BAD_SERIALIED = "THIS IS NOT JSON\n"
TMP_DIR = None
COUNT = 0


def setup():
    """Set up for tests."""
    global TMP_DIR
    TMP_DIR = mkdtemp()


def teardown():
    """Clean up after tests."""
    for fname in os.listdir(TMP_DIR):
        os.remove(os.path.join(TMP_DIR, fname))
    os.rmdir(TMP_DIR)


def _new_file():
    """Return a new json file path each time."""
    global COUNT
    COUNT += 1
    return os.path.join(TMP_DIR, f"test{COUNT}.json")


def test_save_and_load():
    """Test saving and loading back."""
    fname = _new_file()
    save_json(fname, TEST_JSON_A)
    data = load_json(fname)
    assert data == TEST_JSON_A


def test_save_deterministic():
    """Test saving saves the keys ordered."""
    fname = _new_file()
    save_json(fname, {letter: 0 for letter in string.ascii_lowercase})
    with open(fname) as fil:
        raw = fil.read()
    order = [raw.index(letter) for letter in string.ascii_lowercase]
    assert sorted(order) == order


# Skipped on Windows
@unittest.skipIf(
    sys.platform.startswith("win"), "private permissions not supported on Windows"
)
def test_save_and_load_private():
    """Test we can load private files and that they are protected."""
    fname = _new_file()
    save_json(fname, TEST_JSON_A, private=True)
    data = load_json(fname)
    assert data == TEST_JSON_A
    stats = os.stat(fname)
    assert stats.st_mode & 0o77 == 0


def test_overwrite_and_reload():
    """Test that we can overwrite an existing file and read back."""
    fname = _new_file()
    save_json(fname, TEST_JSON_A)
    save_json(fname, TEST_JSON_B)
    data = load_json(fname)
    assert data == TEST_JSON_B


def test_save_bad_data():
    """Test error from trying to save unserialisable data."""
    fname = _new_file()
    with pytest.raises(SerializationError) as excinfo:
        save_json(fname, {"hello": set()})

    assert (
        f"Failed to serialize to JSON: {fname}. Bad data at $.hello=set()(<class 'set'>"
        in str(excinfo.value)
    )


def test_load_bad_data():
    """Test error from trying to load unserialisable data."""
    fname = _new_file()
    with open(fname, "w") as fil:
        fil.write(TEST_BAD_SERIALIED)
    with pytest.raises(HomeAssistantError):
        load_json(fname)


def test_custom_encoder():
    """Test serializing with a custom encoder."""

    class MockJSONEncoder(JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            return "9"

    fname = _new_file()
    save_json(fname, Mock(), encoder=MockJSONEncoder)
    data = load_json(fname)
    assert data == "9"


def test_find_unserializable_data():
    """Find unserializeable data."""
    assert find_paths_unserializable_data(1) == {}
    assert find_paths_unserializable_data([1, 2]) == {}
    assert find_paths_unserializable_data({"something": "yo"}) == {}

    assert find_paths_unserializable_data({"something": set()}) == {
        "$.something": set()
    }
    assert find_paths_unserializable_data({"something": [1, set()]}) == {
        "$.something[1]": set()
    }
    assert find_paths_unserializable_data([1, {"bla": set(), "blub": set()}]) == {
        "$[1].bla": set(),
        "$[1].blub": set(),
    }
    assert find_paths_unserializable_data({("A",): 1}) == {"$<key: ('A',)>": ("A",)}
    assert math.isnan(
        find_paths_unserializable_data(
            float("nan"), dump=partial(dumps, allow_nan=False)
        )["$"]
    )

    # Test custom encoder + State support.

    class MockJSONEncoder(JSONEncoder):
        """Mock JSON encoder."""

        def default(self, o):
            """Mock JSON encode method."""
            if isinstance(o, datetime):
                return o.isoformat()
            return super().default(o)

    bad_data = object()

    assert (
        find_paths_unserializable_data(
            [State("mock_domain.mock_entity", "on", {"bad": bad_data})],
            dump=partial(dumps, cls=MockJSONEncoder),
        )
        == {"$[0](state: mock_domain.mock_entity).attributes.bad": bad_data}
    )

    assert (
        find_paths_unserializable_data(
            [Event("bad_event", {"bad_attribute": bad_data})],
            dump=partial(dumps, cls=MockJSONEncoder),
        )
        == {"$[0](event: bad_event).data.bad_attribute": bad_data}
    )
