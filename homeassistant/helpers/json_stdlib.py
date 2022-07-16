"""Helpers to help with encoding Home Assistant objects in JSON."""

import datetime
import json
from typing import Any

JSON_ENCODE_EXCEPTIONS = (TypeError, ValueError)
JSON_DECODE_EXCEPTIONS = (json.JSONDecodeError,)

json_dumps = json.dumps
json_loads = json.loads


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
    return json.dumps(data, cls=JSONEncoder).encode("utf-8")


def json_dumps_indent(data: Any) -> str:
    """Dump json string with array and object members indented."""
    return json.dumps(data, cls=JSONEncoder, indent=2)


def json_dumps_indent_no_encoder(data: Any) -> str:
    """Dump json string with array and object members indented.
    Do not apply the HASS default encoder."""
    return json.dumps(data, indent=2)


def json_dumps_sorted(data: Any) -> str:
    """Dump json string with keys sorted."""
    return json.dumps(data, cls=JSONEncoder, sort_keys=True)
