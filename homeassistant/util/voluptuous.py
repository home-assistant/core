"""Helpers for dealing with the voluptuous validator."""
import json
from typing import Any

import voluptuous as vol


def _nested_getitem(data: Any, ex: vol.Invalid) -> Any:
    """Try to find the configuration of the voluptuous configuration error."""
    for item_index in ex.path:
        try:
            data = data[item_index]
        except (KeyError, IndexError, TypeError):
            return None
    return data


def humanize_error(config: Any, ex: vol.Invalid) -> str:
    """Generate a human-readable representation of the voluptuous exception."""
    offending_item = _nested_getitem(config, ex)
    if isinstance(offending_item, dict):
        try:
            # Try to use JSON for dictionaries - otherwise
            # the user will be greeted by a nice "OrderedDict([("key", ...)])
            # message
            offending_item = json.dumps(offending_item)
        except (ValueError, TypeError):
            # Was not JSON-serializable, fallback to __str__
            pass
    return '{}. Got {}'.format(ex, offending_item)
