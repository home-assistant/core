"""Config validation for the Z-Wave JS integration."""
from typing import Any

import voluptuous as vol

import homeassistant.helpers.config_validation as cv

# Validates that a bitmask is provided in hex form and converts it to decimal
# int equivalent since that's what the library uses
BITMASK_SCHEMA = vol.All(
    cv.string,
    vol.Lower,
    vol.Match(
        r"^(0x)?[0-9a-f]+$",
        msg="Must provide an integer (e.g. 255) or a bitmask in hex form (e.g. 0xff)",
    ),
    lambda value: int(value, 16),
)


def boolean(value: Any) -> bool:
    """Validate and coerce a boolean value."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        value = value.lower().strip()
        if value in ("true", "yes", "on", "enable"):
            return True
        if value in ("false", "no", "off", "disable"):
            return False
    raise vol.Invalid(f"invalid boolean value {value}")


VALUE_SCHEMA = vol.Any(
    boolean,
    vol.Coerce(int),
    vol.Coerce(float),
    BITMASK_SCHEMA,
    cv.string,
    dict,
)
