"""Tests for the :mod:`hass_client.messages` JSON-bytes wire codec.

Dynamic payloads cross as orjson-encoded bytes, so numbers keep their native
types end to end — an ``int`` stays ``int``, a ``float`` stays ``float``, and
big ints don't lose precision to a double (the failure modes of the
``google.protobuf.Struct`` wire this replaced).
"""

from hass_client.messages import decode_json, decode_json_dict, encode_json


def test_json_round_trip_preserves_number_types() -> None:
    """Ints stay int and floats stay float across the wire."""
    out = decode_json_dict(
        encode_json({"port": 8123, "level": 255, "ratio": 0.5, "zero": 0})
    )

    assert isinstance(out["port"], int)
    assert out["port"] == 8123
    assert isinstance(out["level"], int)
    assert isinstance(out["zero"], int)
    assert isinstance(out["ratio"], float)
    assert out["ratio"] == 0.5


def test_json_round_trip_number_fidelity() -> None:
    """Whole-number floats stay float; ints past 2**53 stay exact."""
    out = decode_json_dict(
        encode_json({"whole_float": 2.0, "int": 255, "big": 2**53 + 1})
    )

    assert isinstance(out["whole_float"], float)
    assert out["whole_float"] == 2.0
    assert isinstance(out["int"], int)
    assert out["int"] == 255
    assert isinstance(out["big"], int)
    assert out["big"] == 2**53 + 1


def test_json_round_trip_nested_and_lists() -> None:
    """Number fidelity holds in nested dicts and lists."""
    out = decode_json_dict(encode_json({"nested": {"v": 1}, "items": [1, 2.5, 3]}))

    assert isinstance(out["nested"]["v"], int)
    assert [type(item) for item in out["items"]] == [int, float, int]


def test_store_envelope_version_is_int() -> None:
    """The store envelope's version fields survive the wire as ints."""
    out = decode_json_dict(
        encode_json({"version": 1, "minor_version": 2, "key": "demo", "data": []})
    )

    assert isinstance(out["version"], int)
    assert isinstance(out["minor_version"], int)


def test_decode_json_empty_bytes() -> None:
    """Empty bytes mean an absent payload: None (or {} for dict callers)."""
    assert decode_json(b"") is None
    assert decode_json_dict(b"") == {}
