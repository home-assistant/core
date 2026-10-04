"""Config entry option helpers for Amcrest."""

from typing import cast

from homeassistant.config_entries import ConfigEntry


def get_platform_keys(entry: ConfigEntry, option_key: str) -> list[str]:
    """Return platform keys for a config entry."""
    return cast(list[str], entry.options[option_key])
