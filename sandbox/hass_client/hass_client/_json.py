"""Shared JSON coercion for the sandbox client package.

A single source of truth for turning rich Home Assistant objects (sets, enums,
``as_dict`` objects, datetimes, …) into the plain dict/list/scalar shapes the
wire accepts. Implemented as a round-trip through the mirrored
:mod:`messages` codec so the coercion rules cannot drift from what
:func:`messages.encode_json` puts on the wire.
"""

from typing import Any

from .messages import decode_json, encode_json


def json_safe(value: Any) -> Any:
    """Return ``value`` coerced to plain JSON-safe Python objects.

    Round-trips through the wire codec's HA-aware encoder (``as_dict``/set/
    enum-aware, with a ``str()`` fallback for unknown objects) so callers get
    plain dict/list/scalar shapes.
    """
    return decode_json(encode_json(value))
