"""Config entry option helpers for Amcrest."""

from typing import cast

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry


def get_platform_keys(
    entry: ConfigEntry,
    option_key: str,
    ui_defaults: list[str],
) -> list[str]:
    """Return platform keys for a config entry."""
    if entry.source == SOURCE_IMPORT:
        return cast(list[str], entry.options.get(option_key, []))
    if option_key in entry.options:
        return cast(list[str], entry.options[option_key])
    return ui_defaults
