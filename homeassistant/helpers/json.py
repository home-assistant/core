"""Helpers to help with encoding Home Assistant objects in JSON."""

from typing import Final

from .json_stdlib import JSONEncoder, ExtendedJSONEncoder

try:
    import orjson
except ImportError:
    from .json_stdlib import (
        JSON_ENCODE_EXCEPTIONS,
        JSON_DECODE_EXCEPTIONS,
        json_bytes,
        json_dumps,
        json_dumps_sorted,
        json_loads,
    )
else:
    from .json_orjson import (
        JSON_ENCODE_EXCEPTIONS,
        JSON_DECODE_EXCEPTIONS,
        json_bytes,
        json_dumps,
        json_dumps_sorted,
        json_loads,
    )

JSON_DUMP: Final = json_dumps
