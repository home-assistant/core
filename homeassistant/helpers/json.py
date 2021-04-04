"""Helpers to help with encoding Home Assistant objects in JSON."""
from datetime import datetime, timedelta
import json
from typing import Any


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    def default(self, o: Any) -> Any:
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        if isinstance(o, timedelta):
            return o.total_seconds()
        if hasattr(o, "as_dict"):
            return o.as_dict()

        return json.JSONEncoder.default(self, o)
