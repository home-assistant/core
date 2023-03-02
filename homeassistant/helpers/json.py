"""Helpers to help with encoding Home Assistant objects in JSON."""
import datetime
import json
from pathlib import Path
from typing import Any, Final

import orjson

JSON_ENCODE_EXCEPTIONS = (TypeError, ValueError)
JSON_DECODE_EXCEPTIONS = (orjson.JSONDecodeError,)


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    def default(self, o: Any) -> Any:
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        if hasattr(o, "as_dict"):
            return o.as_dict()

        return json.JSONEncoder.default(self, o)


def json_encoder_default(obj: Any) -> Any:
    """Convert Home Assistant objects.

    Hand other objects to the original method.
    """
    if isinstance(obj, (set, tuple)):
        return list(obj)
    if isinstance(obj, float):
        return float(obj)
    if hasattr(obj, "as_dict"):
        return obj.as_dict()
    if isinstance(obj, Path):
        return obj.as_posix()
    raise TypeError


class ExtendedJSONEncoder(JSONEncoder):
    """JSONEncoder that supports Home Assistant objects and falls back to repr(o)."""

    def default(self, o: Any) -> Any:
        """Convert certain objects.

        Fall back to repr(o).
        """
        if isinstance(o, datetime.timedelta):
            return {"__type": str(type(o)), "total_seconds": o.total_seconds()}
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        if isinstance(o, (datetime.date, datetime.time)):
            return {"__type": str(type(o)), "isoformat": o.isoformat()}
        try:
            return super().default(o)
        except TypeError:
            return {"__type": str(type(o)), "repr": repr(o)}


def json_bytes(data: Any) -> bytes:
    """Dump json bytes."""
    return orjson.dumps(
        data, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
    )


def json_bytes_strip_null(data: Any) -> bytes:
    """Dump json bytes after terminating strings at the first NUL."""

    def process_dict(_dict: dict[Any, Any]) -> dict[Any, Any]:
        """Strip NUL from items in a dict."""
        return {key: strip_null(o) for key, o in _dict.items()}

    def process_list(_list: list[Any]) -> list[Any]:
        """Strip NUL from items in a list."""
        return [strip_null(o) for o in _list]

    def strip_null(obj: Any) -> Any:
        """Strip NUL from an object."""
        if isinstance(obj, str):
            return obj.split("\0", 1)[0]
        if isinstance(obj, dict):
            return process_dict(obj)
        if isinstance(obj, list):
            return process_list(obj)
        return obj

    # We expect null-characters to be very rare, hence try encoding first and look
    # for an escaped null-character in the output.
    result = json_bytes(data)
    if b"\\u0000" in result:
        # We work on the processed result so we don't need to worry about
        # Home Assistant extensions which allows encoding sets, tuples, etc.
        data_processed = orjson.loads(result)
        data_processed = strip_null(data_processed)
        result = json_bytes(data_processed)

    return result


def json_dumps(data: Any) -> str:
    """Dump json string.

    orjson supports serializing dataclasses natively which
    eliminates the need to implement as_dict in many places
    when the data is already in a dataclass. This works
    well as long as all the data in the dataclass can also
    be serialized.

    If it turns out to be a problem we can disable this
    with option |= orjson.OPT_PASSTHROUGH_DATACLASS and it
    will fallback to as_dict
    """
    return orjson.dumps(
        data, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
    ).decode("utf-8")


def json_dumps_sorted(data: Any) -> str:
    """Dump json string with keys sorted."""
    return orjson.dumps(
        data,
        option=orjson.OPT_NON_STR_KEYS | orjson.OPT_SORT_KEYS,
        default=json_encoder_default,
    ).decode("utf-8")


json_loads = orjson.loads


JSON_DUMP: Final = json_dumps
