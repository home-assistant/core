"""Helpers to help with encoding Home Assistant objects in JSON."""
from datetime import datetime
from json import JSONEncoder as DefaultJSONEncoder
from typing import Any


class JSONEncoder(DefaultJSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    def default(self, o: Any) -> Any:
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        try:
            return DefaultJSONEncoder.default(self, o)
        except TypeError:
            if isinstance(o, datetime):
                return o.isoformat()
            if isinstance(o, set):
                return list(o)
            if hasattr(o, "as_dict"):
                return o.as_dict()
            raise
