"""Shared utilities for the Daikin Onecta integration."""

import re


def enum_value_to_state(value: str) -> str:
    """Normalize Daikin's camelCase enum values for Home Assistant states."""
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).lower()


def is_read_only_on_off_value(settable: bool, values: list[str] | None) -> bool:
    """Return whether a characteristic is a read-only on/off string value."""
    return not settable and values is not None and set(values) == {"on", "off"}
