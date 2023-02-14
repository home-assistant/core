"""JSON decode utility functions."""
from __future__ import annotations

from collections.abc import Callable

import orjson

JSON_DECODE_EXCEPTIONS = (orjson.JSONDecodeError,)

JsonValueType = (
    dict[str, "JsonValueType"] | list["JsonValueType"] | str | int | float | bool | None
)
"""Any data that can be returned by the standard JSON deserializing process."""
JsonObjectType = dict[str, JsonValueType]
"""Dictionary that can be returned by the standard JSON deserializing process."""


json_loads: Callable[[bytes | bytearray | memoryview | str], JsonValueType]
json_loads = orjson.loads
"""Parse JSON data."""


def json_loads_object(__obj: bytes | bytearray | memoryview | str) -> JsonObjectType:
    """Parse JSON data and ensure result is a dictionary."""
    value: JsonValueType = json_loads(__obj)
    # Avoid isinstance overhead as we are not interested in dict subclasses
    if type(value) is dict:  # pylint: disable=unidiomatic-typecheck
        return value
    raise ValueError(f"Expected JSON to be parsed as a dict got {type(value)}")
