"""Utility functions for the Solyx Energy integration."""

import logging
from typing import Any

_LOGGER = logging.getLogger(__name__)


def parse_attr_value(raw: dict[str, Any], attr_name: str) -> Any:
    """Extract a value from a Solyx device attribute."""
    attributes = raw.get("attributes") or {}
    value = attributes.get(attr_name, {}).get("value")
    _LOGGER.debug("Extracting %s. New value: %s", attr_name, value)
    return value


def parse_float(raw: dict[str, Any], attr_name: str) -> float | None:
    """Parse a float value from a Solyx device attribute."""
    value = parse_attr_value(raw, attr_name)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as _err:
        _LOGGER.warning("Unable to parse float value %s", value)
        return None
