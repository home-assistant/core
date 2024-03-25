"""Config Helper for Transport for London (TfL) module."""
from types import MappingProxyType
from typing import Any

from homeassistant.config_entries import ConfigEntry


def config_from_entry(
    entry: ConfigEntry,
) -> dict[str, Any] | MappingProxyType[str, Any]:
    """Get config for the TfL integration from the config entry. Gets it from options or data."""
    # This is needed because HA doesn't allow you to update the original data
    return entry.options if entry.options else entry.data
