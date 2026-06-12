"""Wire-fidelity tests for the main-side ``sandbox.messages`` mirror.

``messages.py`` is hand-mirrored between main and the client runtime; this
pins the int-coercion behaviour (Phase 7) on the main copy, where state
attributes, capabilities, and store data are decoded from the Struct wire.
"""

from homeassistant.components.sandbox.messages import (
    dict_to_struct,
    list_to_listvalue,
    listvalue_to_list,
    struct_to_dict,
)


def test_struct_round_trip_preserves_int() -> None:
    """Whole-number values decode as int; fractional ones stay float."""
    out = struct_to_dict(dict_to_struct({"brightness": 255, "ratio": 0.5, "count": 0}))

    assert isinstance(out["brightness"], int)
    assert out["brightness"] == 255
    assert isinstance(out["count"], int)
    assert isinstance(out["ratio"], float)
    assert out["ratio"] == 0.5


def test_struct_round_trip_preserves_int_in_nested_and_lists() -> None:
    """Coercion recurses into nested structs and lists."""
    out = struct_to_dict(dict_to_struct({"nested": {"v": 1}, "items": [1, 2.5, 3]}))

    assert isinstance(out["nested"]["v"], int)
    assert [type(item) for item in out["items"]] == [int, float, int]


def test_listvalue_round_trip_preserves_int() -> None:
    """``ListValue`` coercion matches the Struct path."""
    out = listvalue_to_list(list_to_listvalue([1, 2.5, 3]))

    assert [type(item) for item in out] == [int, float, int]
