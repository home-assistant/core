"""Helpers to help with encoding Home Assistant objects in JSON."""

__all__ = [
    "ExtendedJSONEncoder",
    "JSONEncoder",
    "JSON_DUMP",
    "JSON_ENCODE_EXCEPTIONS",
    "JSON_DECODE_EXCEPTIONS",
    "json_bytes",
    "json_dumps",
    "json_dumps_indent",
    "json_dumps_indent_no_encoder",
    "json_dumps_sorted",
    "json_loads",
]

from typing import Final

from .json_stdlib import JSONEncoder, ExtendedJSONEncoder

try:
    from .json_orjson import (
        JSON_ENCODE_EXCEPTIONS,
        JSON_DECODE_EXCEPTIONS,
        json_bytes,
        json_dumps,
        json_dumps_indent,
        json_dumps_indent_no_encoder,
        json_dumps_sorted,
        json_loads,
    )
except ImportError:
    from .json_stdlib import (
        JSON_ENCODE_EXCEPTIONS,
        JSON_DECODE_EXCEPTIONS,
        json_bytes,
        json_dumps,
        json_dumps_indent,
        json_dumps_indent_no_encoder,
        json_dumps_sorted,
        json_loads,
    )

JSON_DUMP: Final = json_dumps
