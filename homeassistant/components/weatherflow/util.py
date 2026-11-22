"""Utilities for the WeatherFlow integration."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from . import WeatherFlowConfigEntry


def format_dispatch_call(config_entry: WeatherFlowConfigEntry) -> str:
    """Construct a dispatch call from a ConfigEntry."""
    return f"{config_entry.domain}_{config_entry.entry_id}_add"
