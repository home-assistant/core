"""JSON utility functions."""
from __future__ import annotations

from collections.abc import Callable
import json
import logging
from os import PathLike
from typing import Any

import orjson

from homeassistant.exceptions import HomeAssistantError

from .file import WriteError  # pylint: disable=unused-import # noqa: F401

_SENTINEL = object()
_LOGGER = logging.getLogger(__name__)

JsonValueType = (
    dict[str, "JsonValueType"] | list["JsonValueType"] | str | int | float | bool | None
)
"""Any data that can be returned by the standard JSON deserializing process."""
JsonArrayType = list[JsonValueType]
"""List that can be returned by the standard JSON deserializing process."""
JsonObjectType = dict[str, JsonValueType]
"""Dictionary that can be returned by the standard JSON deserializing process."""

JSON_ENCODE_EXCEPTIONS = (TypeError, ValueError)
JSON_DECODE_EXCEPTIONS = (orjson.JSONDecodeError,)


class SerializationError(HomeAssistantError):
    """Error serializing the data to JSON."""


json_loads: Callable[[bytes | bytearray | memoryview | str], JsonValueType]
json_loads = orjson.loads
"""Parse JSON data."""


def json_loads_array(__obj: bytes | bytearray | memoryview | str) -> JsonArrayType:
    """Parse JSON data and ensure result is a list."""
    value: JsonValueType = json_loads(__obj)
    # Avoid isinstance overhead as we are not interested in list subclasses
    if type(value) is list:  # pylint: disable=unidiomatic-typecheck
        return value
    raise ValueError(f"Expected JSON to be parsed as a list got {type(value)}")


def json_loads_object(__obj: bytes | bytearray | memoryview | str) -> JsonObjectType:
    """Parse JSON data and ensure result is a dictionary."""
    value: JsonValueType = json_loads(__obj)
    # Avoid isinstance overhead as we are not interested in dict subclasses
    if type(value) is dict:  # pylint: disable=unidiomatic-typecheck
        return value
    raise ValueError(f"Expected JSON to be parsed as a dict got {type(value)}")


def load_json(
    filename: str | PathLike, default: JsonValueType = _SENTINEL  # type: ignore[assignment]
) -> JsonValueType:
    """Load JSON data from a file.

    Defaults to returning empty dict if file is not found.
    """
    try:
        with open(filename, encoding="utf-8") as fdesc:
            return orjson.loads(fdesc.read())  # type: ignore[no-any-return]
    except FileNotFoundError:
        # This is not a fatal error
        _LOGGER.debug("JSON file not found: %s", filename)
    except ValueError as error:
        _LOGGER.exception("Could not parse JSON content: %s", filename)
        raise HomeAssistantError(error) from error
    except OSError as error:
        _LOGGER.exception("JSON file reading failed: %s", filename)
        raise HomeAssistantError(error) from error
    return {} if default is _SENTINEL else default


def load_json_array(
    filename: str | PathLike, default: JsonArrayType = _SENTINEL  # type: ignore[assignment]
) -> JsonArrayType:
    """Load JSON data from a file and return as list.

    Defaults to returning empty list if file is not found.
    """
    if default is _SENTINEL:
        default = []
    value: JsonValueType = load_json(filename, default=default)
    # Avoid isinstance overhead as we are not interested in list subclasses
    if type(value) is list:  # pylint: disable=unidiomatic-typecheck
        return value
    _LOGGER.exception(
        "Expected JSON to be parsed as a list got %s in: %s", {type(value)}, filename
    )
    raise HomeAssistantError(f"Expected JSON to be parsed as a list got {type(value)}")


def load_json_object(
    filename: str | PathLike, default: JsonObjectType = _SENTINEL  # type: ignore[assignment]
) -> JsonObjectType:
    """Load JSON data from a file and return as dict.

    Defaults to returning empty dict if file is not found.
    """
    if default is _SENTINEL:
        default = {}
    value: JsonValueType = load_json(filename, default=default)
    # Avoid isinstance overhead as we are not interested in dict subclasses
    if type(value) is dict:  # pylint: disable=unidiomatic-typecheck
        return value
    _LOGGER.exception(
        "Expected JSON to be parsed as a dict got %s in: %s", {type(value)}, filename
    )
    raise HomeAssistantError(f"Expected JSON to be parsed as a dict got {type(value)}")


def save_json(
    filename: str,
    data: list | dict,
    private: bool = False,
    *,
    encoder: type[json.JSONEncoder] | None = None,
    atomic_writes: bool = False,
) -> None:
    """Save JSON data to a file."""
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers.frame import report

    report(
        (
            "uses save_json from homeassistant.util.json module."
            " This is deprecated and will stop working in Home Assistant 2022.4, it"
            " should be updated to use homeassistant.helpers.json module instead"
        ),
        error_if_core=False,
    )

    # pylint: disable-next=import-outside-toplevel
    import homeassistant.helpers.json as json_helper

    json_helper.save_json(
        filename, data, private, encoder=encoder, atomic_writes=atomic_writes
    )


def format_unserializable_data(data: dict[str, Any]) -> str:
    """Format output of find_paths in a friendly way.

    Format is comma separated: <path>=<value>(<type>)
    """
    return ", ".join(f"{path}={value}({type(value)}" for path, value in data.items())


def find_paths_unserializable_data(
    bad_data: Any, *, dump: Callable[[Any], str] = json.dumps
) -> dict[str, Any]:
    """Find the paths to unserializable data.

    This method is slow! Only use for error handling.
    """
    # pylint: disable-next=import-outside-toplevel
    from homeassistant.helpers.frame import report

    report(
        (
            "uses find_paths_unserializable_data from homeassistant.util.json module."
            " This is deprecated and will stop working in Home Assistant 2022.4, it"
            " should be updated to use homeassistant.helpers.json module instead"
        ),
        error_if_core=False,
    )

    # pylint: disable-next=import-outside-toplevel
    import homeassistant.helpers.json as json_helper

    return json_helper.find_paths_unserializable_data(bad_data, dump=dump)
