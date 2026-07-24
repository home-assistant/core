"""Utility file with several parsing functions for the Solyx Energy Nymo integration."""

import logging
import re
from typing import Any

_LOGGER = logging.getLogger(__name__)


def parse_attr_value(raw: dict[str, Any], attr_name: str) -> Any:
    """Extract value from a Solyx device attribute."""
    attributes = raw.get("attributes") or {}
    val = attributes.get(attr_name, {}).get("value")
    _LOGGER.debug("Extracting %s. New value: %s", attr_name, val)
    return val


def parse_float(raw: dict[str, Any], attr_name: str) -> float | None:
    """Parse a float value from a Solyx device attribute."""
    val = parse_attr_value(raw, attr_name)
    if val is None:
        return None
    try:
        return float(val)
    except TypeError, ValueError:
        _LOGGER.warning("Unable to parse float value %s", val)
        return None


def camel_to_snake(name: str) -> str:
    """Convert a camelCase attribute name to a snake_case translation key."""
    return re.compile(r"(?<!^)(?=[A-Z])").sub("_", name).lower()
