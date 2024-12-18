"""JSON utility functions."""

from __future__ import annotations

import logging
from os import PathLike
from typing import Any

import orjson

from homeassistant.exceptions import HomeAssistantError

_SENTINEL = object()
_LOGGER = logging.getLogger(__name__)

type JsonValueType = (
    dict[str, JsonValueType] | list[JsonValueType] | str | int | float | bool | None
)
"""Any data that can be returned by the standard JSON deserializing process."""
type JsonArrayType = list[JsonValueType]
"""List that can be returned by the standard JSON deserializing process."""
type JsonObjectType = dict[str, JsonValueType]
"""Dictionary that can be returned by the standard JSON deserializing process."""

JSON_ENCODE_EXCEPTIONS = (TypeError, ValueError)
JSON_DECODE_EXCEPTIONS = (orjson.JSONDecodeError,)


class SerializationError(HomeAssistantError):
    """Error serializing the data to JSON."""


def json_loads(obj: bytes | bytearray | memoryview | str, /) -> JsonValueType:
    """Parse JSON data.

    This adds a workaround for orjson not handling subclasses of str,
    https://github.com/ijl/orjson/issues/445.
    """
    # Avoid isinstance overhead for the common case
    if type(obj) not in (bytes, bytearray, memoryview, str) and isinstance(obj, str):
        return orjson.loads(str(obj))  # type:ignore[no-any-return]
    return orjson.loads(obj)  # type:ignore[no-any-return]


def json_loads_array(obj: bytes | bytearray | memoryview | str, /) -> JsonArrayType:
    """Parse JSON data and ensure result is a list."""
    value: JsonValueType = json_loads(obj)
    # Avoid isinstance overhead as we are not interested in list subclasses
    if type(value) is list:  # noqa: E721
        return value
    raise ValueError(f"Expected JSON to be parsed as a list got {type(value)}")


def json_loads_object(obj: bytes | bytearray | memoryview | str, /) -> JsonObjectType:
    """Parse JSON data and ensure result is a dictionary."""
    value: JsonValueType = json_loads(obj)
    # Avoid isinstance overhead as we are not interested in dict subclasses
    if type(value) is dict:  # noqa: E721
        return value
    raise ValueError(f"Expected JSON to be parsed as a dict got {type(value)}")


def load_json(
    filename: str | PathLike[str],
    default: JsonValueType = _SENTINEL,  # type: ignore[assignment]
) -> JsonValueType:
    """Load JSON data from a file.

    Defaults to returning empty dict if file is not found.
    """
    try:
        with open(filename, mode="rb") as fdesc:
            return orjson.loads(fdesc.read())  # type: ignore[no-any-return]
    except FileNotFoundError:
        # This is not a fatal error
        _LOGGER.debug("JSON file not found: %s", filename)
    except JSON_DECODE_EXCEPTIONS as error:
        _LOGGER.exception("Could not parse JSON content: %s", filename)
        raise HomeAssistantError(f"Error while loading {filename}: {error}") from error
    except OSError as error:
        _LOGGER.exception("JSON file reading failed: %s", filename)
        raise HomeAssistantError(f"Error while loading {filename}: {error}") from error
    return {} if default is _SENTINEL else default


def load_json_array(
    filename: str | PathLike[str],
    default: JsonArrayType = _SENTINEL,  # type: ignore[assignment]
) -> JsonArrayType:
    """Load JSON data from a file and return as list.

    Defaults to returning empty list if file is not found.
    """
    if default is _SENTINEL:
        default = []
    value: JsonValueType = load_json(filename, default=default)
    # Avoid isinstance overhead as we are not interested in list subclasses
    if type(value) is list:  # noqa: E721
        return value
    _LOGGER.exception(
        "Expected JSON to be parsed as a list got %s in: %s", {type(value)}, filename
    )
    raise HomeAssistantError(f"Expected JSON to be parsed as a list got {type(value)}")


def load_json_object(
    filename: str | PathLike[str],
    default: JsonObjectType = _SENTINEL,  # type: ignore[assignment]
) -> JsonObjectType:
    """Load JSON data from a file and return as dict.

    Defaults to returning empty dict if file is not found.
    """
    if default is _SENTINEL:
        default = {}
    value: JsonValueType = load_json(filename, default=default)
    # Avoid isinstance overhead as we are not interested in dict subclasses
    if type(value) is dict:  # noqa: E721
        return value
    _LOGGER.exception(
        "Expected JSON to be parsed as a dict got %s in: %s", {type(value)}, filename
    )
    raise HomeAssistantError(f"Expected JSON to be parsed as a dict got {type(value)}")


def format_unserializable_data(data: dict[str, Any]) -> str:
    """Format output of find_paths in a friendly way.

    Format is comma separated: <path>=<value>(<type>)
    """
    return ", ".join(f"{path}={value}({type(value)}" for path, value in data.items())
