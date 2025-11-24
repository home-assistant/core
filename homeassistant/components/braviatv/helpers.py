"""Helper functions for Bravia TV integration."""

from __future__ import annotations

from typing import Any

# Type alias for picture settings data from Sony API
type PictureSettingsData = list[dict[str, Any]] | None


def get_picture_setting(
    data: PictureSettingsData, target: str
) -> dict[str, Any] | None:
    """Get the full picture setting dict for a target.

    Args:
        data: List of picture settings from Sony API
        target: The setting target name (e.g., "brightness", "pictureMode")

    Returns:
        The setting dict if found, None otherwise
    """
    if not data:
        return None
    for setting in data:
        if setting.get("target") == target:
            return setting
    return None


def is_numeric_setting(setting: dict[str, Any]) -> bool:
    """Check if a setting is a numeric type (not an enum).

    Sony API returns two formats for candidates:
    - Enum: [{"value": "dvDark"}, {"value": "dvBright"}] or ["vivid", "standard"]
    - Numeric: [{"max": 50, "min": 0, "step": 1}]

    Args:
        setting: A single picture setting dict from Sony API

    Returns:
        True if the setting is numeric, False if it's an enum
    """
    candidates = setting.get("candidate")

    # If candidates is None or empty list, check if currentValue is numeric
    if not candidates:
        current_value = setting.get("currentValue")
        if current_value is None:
            return True  # Assume numeric if no value yet
        if isinstance(current_value, int):
            return True
        if isinstance(current_value, str):
            try:
                int(current_value)
            except ValueError:
                return False
            else:
                return True
        return False

    first_candidate = candidates[0]

    # If first candidate is a string, it's an enum
    if isinstance(first_candidate, str):
        return False

    # If first candidate is a dict, check what keys it has
    if isinstance(first_candidate, dict):
        # Dict with "value" key = enum (e.g., {"value": "dvDark"})
        if "value" in first_candidate:
            return False
        # Dict with "min"/"max"/"step" keys = numeric
        if "min" in first_candidate or "max" in first_candidate:
            return True

    return False


def is_enum_setting(setting: dict[str, Any]) -> bool:
    """Check if a setting is an enum type (not numeric).

    This is the inverse of is_numeric_setting, but with slightly different
    default behavior for edge cases.

    Args:
        setting: A single picture setting dict from Sony API

    Returns:
        True if the setting is an enum, False if it's numeric
    """
    candidates = setting.get("candidate")

    # If no candidates, check if currentValue is non-numeric string
    if not candidates:
        current_value = setting.get("currentValue")
        if current_value is None:
            return False  # Can't determine type without value
        if isinstance(current_value, int):
            return False  # Numeric
        if isinstance(current_value, str):
            try:
                int(current_value)
            except ValueError:
                return True  # Non-numeric string = enum
            else:
                return False  # Numeric string
        return False

    first_candidate = candidates[0]

    # If first candidate is a string, it's an enum (simple format)
    if isinstance(first_candidate, str):
        return True

    # If first candidate is a dict, check what keys it has
    if isinstance(first_candidate, dict):
        # Dict with "value" key = enum (e.g., {"value": "dvDark"})
        if "value" in first_candidate:
            return True
        # Dict with "min"/"max"/"step" keys = numeric
        if "min" in first_candidate or "max" in first_candidate:
            return False

    return False


def is_picture_setting_available(data: PictureSettingsData, target: str) -> bool:
    """Check if picture setting is currently available.

    The Sony API includes an isAvailable field that indicates if the setting
    is currently functional (e.g., some settings may be disabled depending
    on the current picture mode or input source).

    Args:
        data: List of picture settings from Sony API
        target: The setting target name

    Returns:
        True if the setting is available, False otherwise
    """
    setting = get_picture_setting(data, target)
    if not setting:
        return False

    # Sony API: isAvailable indicates if the setting is currently functional
    # Default to True if field is not present (backward compatibility)
    return bool(setting.get("isAvailable", True))
