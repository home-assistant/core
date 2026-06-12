"""Tests for :mod:`hass_client.messages` Struct/ListValue wire fidelity.

``google.protobuf.Struct`` stores every number as a double, so an ``int``
crossing inside a dynamic field would otherwise come back a ``float``.
``_value_to_py`` restores whole-number floats to ``int`` while leaving
genuinely fractional values alone.
"""

from hass_client.messages import (
    dict_to_struct,
    list_to_listvalue,
    listvalue_to_list,
    struct_to_dict,
)


def test_struct_round_trip_preserves_int() -> None:
    """Whole-number values come back as int; fractional ones stay float."""
    out = struct_to_dict(
        dict_to_struct({"port": 8123, "level": 255, "ratio": 0.5, "zero": 0})
    )

    assert isinstance(out["port"], int)
    assert out["port"] == 8123
    assert isinstance(out["level"], int)
    assert isinstance(out["zero"], int)
    assert isinstance(out["ratio"], float)
    assert out["ratio"] == 0.5


def test_struct_round_trip_preserves_int_in_nested_and_lists() -> None:
    """Coercion recurses into nested structs and lists."""
    out = struct_to_dict(
        dict_to_struct({"nested": {"v": 1}, "items": [1, 2.5, 3]})
    )

    assert isinstance(out["nested"]["v"], int)
    assert [type(item) for item in out["items"]] == [int, float, int]


def test_store_envelope_version_is_int() -> None:
    """The store envelope's version fields ride the Struct and stay int."""
    out = struct_to_dict(
        dict_to_struct(
            {"version": 1, "minor_version": 2, "key": "demo", "data": []}
        )
    )

    assert isinstance(out["version"], int)
    assert isinstance(out["minor_version"], int)


def test_listvalue_round_trip_preserves_int() -> None:
    """``ListValue`` coercion matches the Struct path."""
    out = listvalue_to_list(list_to_listvalue([1, 2.5, 3]))

    assert [type(item) for item in out] == [int, float, int]
