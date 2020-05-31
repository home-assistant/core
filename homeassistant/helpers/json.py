"""Helpers to help with encoding Home Assistant objects in JSON."""
from datetime import datetime, timedelta
import json
import logging
from typing import Any

from homeassistant.helpers import template as template_helper

_LOGGER = logging.getLogger(__name__)


class JSONEncoder(json.JSONEncoder):
    """JSONEncoder that supports Home Assistant objects."""

    # pylint: disable=method-hidden
    def default(self, o: Any) -> Any:
        """Convert Home Assistant objects.

        Hand other objects to the original method.
        """
        if isinstance(o, datetime):
            return o.isoformat()
        if isinstance(o, set):
            return list(o)
        if isinstance(o, timedelta):
            return {
                "days": o.days,
                "seconds": o.seconds,
                "microseconds": o.microseconds,
            }
        if isinstance(o, template_helper.Template):
            return o.template
        if hasattr(o, "as_dict"):
            return o.as_dict()

        return json.JSONEncoder.default(self, o)
