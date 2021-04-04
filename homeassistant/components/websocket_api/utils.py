"""Helpers for websocket_api."""
from datetime import timedelta
from typing import Any

from homeassistant.helpers.json import JSONEncoder


class SubscribeTriggerJSONEncoder(JSONEncoder):
    """JSONEncoder that supports timedelta objects and falls back to the Home Assistant Encoder."""

    def default(self, o: Any) -> Any:
        """Convert timedelta objects.

        Hand other objects to the Home Assistant JSONEncoder.
        """
        if isinstance(o, timedelta):
            return o.total_seconds()

        return JSONEncoder.default(self, o)
