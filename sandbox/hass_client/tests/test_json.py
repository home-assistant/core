"""Tests for the shared ``json_safe`` coercion helper.

Covers the behaviour the three former hand-rolled coercers each relied on —
sets/enums/``as_dict`` objects/datetimes (state attrs, capabilities, service
responses) and the ``str()`` fallback for arbitrary objects (best-effort event
data) — so the single helper is a safe replacement for all of them.
"""

from datetime import UTC, datetime
from enum import Enum

from hass_client._json import json_safe


class _Color(Enum):
    RED = "red"


class _HasAsDict:
    def as_dict(self) -> dict[str, str]:
        return {"k": "v"}


class _Opaque:
    def __str__(self) -> str:
        return "opaque!"


def test_sets_become_lists() -> None:
    """Sets coerce to lists (json_encoder_default), elements preserved."""
    result = json_safe({"modes": {"a", "b"}})
    assert isinstance(result["modes"], list)
    assert sorted(result["modes"]) == ["a", "b"]


def test_enum_becomes_value() -> None:
    """Enums coerce to their value."""
    assert json_safe({"c": _Color.RED}) == {"c": "red"}


def test_as_dict_object_is_expanded() -> None:
    """Objects exposing ``as_dict`` expand to that dict."""
    assert json_safe({"o": _HasAsDict()}) == {"o": {"k": "v"}}


def test_datetime_becomes_isoformat() -> None:
    """Datetimes coerce to their ISO-8601 string."""
    moment = datetime(2026, 6, 12, tzinfo=UTC)
    assert json_safe(moment) == moment.isoformat()


def test_unknown_object_falls_back_to_str() -> None:
    """An object the encoder can't handle degrades to ``str(obj)``."""
    assert json_safe({"x": _Opaque()}) == {"x": "opaque!"}


def test_non_str_keys_are_coerced() -> None:
    """Non-string dict keys coerce to strings (OPT_NON_STR_KEYS)."""
    assert json_safe({1: "a"}) == {"1": "a"}


def test_plain_payload_round_trips_unchanged() -> None:
    """Already-JSON-safe structures pass through untouched."""
    payload = {"a": [1, 2], "b": {"c": True}, "d": None}
    assert json_safe(payload) == payload
