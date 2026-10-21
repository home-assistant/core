"""Test read only dictionary."""

import copy
import json
import pickle

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

    with pytest.raises(RuntimeError):
        data |= {"yo": "yo"}

    assert isinstance(data, dict)
    assert dict(data) == {"hello": "world"}
    assert json.dumps(data) == json.dumps({"hello": "world"})

    assert copy.deepcopy(data) == {"hello": "world"}


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_read_only_dict_pickle(protocol: int) -> None:
    """Test read only dictionary survives a pickle round trip."""
    data = ReadOnlyDict({"hello": "world", "nested": {"a": 1}})

    restored = pickle.loads(pickle.dumps(data, protocol=protocol))  # noqa: S301

    assert type(restored) is ReadOnlyDict
    assert restored == {"hello": "world", "nested": {"a": 1}}
