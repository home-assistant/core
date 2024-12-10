"""Functions to unwrap the data from the JSON string."""

import json


def unwrap_int(json_str):
    """Unwrap an integer value from a JSON string."""
    try:
        data = json.loads(json_str)
        return int(data["value"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def unwrap_int_default_0(json_str):
    """Unwrap an integer value from a JSON string, defaulting to 0."""
    try:
        data = json.loads(json_str)
        return int(data["value"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return 0


def unwrap_float(json_str):
    """Unwrap a float value from a JSON string."""
    try:
        data = json.loads(json_str)
        return float(data["value"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None


def unwrap_string(json_str):
    """Unwrap a string value from a JSON string."""
    try:
        data = json.loads(json_str)
        return str(data["value"])
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return None
