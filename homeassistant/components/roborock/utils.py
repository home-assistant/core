"""Utilities for roborock."""


def set_nested_dict(data: dict, key_string: str, value):
    """Set nested dict."""
    here = data
    keys = key_string.split(".")
    for key in keys[:-1]:
        here = here.setdefault(key, {})
    here[keys[-1]] = value


def get_nested_dict(data: dict, key_string: str, default=None) -> dict:
    """Get nested dict."""
    # to-do figure out this function
    here = data
    keys = key_string.split(".")
    for key in keys:
        here = here.get(key)
        if here is None:
            return default
    return here
