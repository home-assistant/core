"""Wire-fidelity tests for the main-side ``sandbox.messages`` mirror.

``messages.py`` is hand-mirrored between main and the client runtime; this
pins the JSON-bytes codec behaviour on the main copy, where state attributes,
capabilities, and store data are decoded from the wire.
"""

from homeassistant.components.sandbox.messages import (
    decode_json,
    decode_json_dict,
    encode_json,
)


def test_json_round_trip_preserves_number_types() -> None:
    """Ints stay int and floats stay float across the wire — natively."""
    out = decode_json_dict(
        encode_json({"brightness": 255, "ratio": 0.5, "count": 0, "level": 2.0})
    )

    assert isinstance(out["brightness"], int)
    assert out["brightness"] == 255
    assert isinstance(out["count"], int)
    assert isinstance(out["ratio"], float)
    assert out["ratio"] == 0.5
    assert isinstance(out["level"], float)
    assert out["level"] == 2.0


def test_json_round_trip_nested_and_lists() -> None:
    """Number fidelity holds in nested dicts and lists."""
    out = decode_json_dict(encode_json({"nested": {"v": 1}, "items": [1, 2.5, 3]}))

    assert isinstance(out["nested"]["v"], int)
    assert [type(item) for item in out["items"]] == [int, float, int]


def test_decode_json_empty_bytes() -> None:
    """Empty bytes mean an absent payload: None (or {} for dict callers)."""
    assert decode_json(b"") is None
    assert decode_json_dict(b"") == {}
