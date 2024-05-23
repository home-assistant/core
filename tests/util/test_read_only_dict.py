"""Test read only dictionary."""

import json

import pytest

from homeassistant.util.read_only_dict import ReadOnlyDict


def test_read_only_dict() -> None:
    """Test read only dictionary."""
    data = ReadOnlyDict({"hello": "world"})

    with pytest.raises(RuntimeError):
        data["hello"] = "universe"

    with pytest.raises(RuntimeError):
        data["other_key"] = "universe"

    with pytest.raises(RuntimeError):
        data.pop("hello")

    with pytest.raises(RuntimeError):
        data.popitem()

    with pytest.raises(RuntimeError):
        data.clear()

    with pytest.raises(RuntimeError):
        data.update({"yo": "yo"})

    with pytest.raises(RuntimeError):
        data.setdefault("yo", "yo")

    assert isinstance(data, dict)
    assert dict(data) == {"hello": "world"}
    assert json.dumps(data) == json.dumps({"hello": "world"})
