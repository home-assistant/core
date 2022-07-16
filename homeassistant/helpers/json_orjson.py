"""Helpers to help with encoding Home Assistant objects in JSON."""

from pathlib import Path
from typing import Any

import orjson

JSON_ENCODE_EXCEPTIONS = (TypeError, ValueError)
JSON_DECODE_EXCEPTIONS = (orjson.JSONDecodeError,)


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


def json_bytes(data: Any) -> bytes:
    """Dump json bytes."""
    return orjson.dumps(
        data, option=orjson.OPT_NON_STR_KEYS, default=json_encoder_default
    )


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
