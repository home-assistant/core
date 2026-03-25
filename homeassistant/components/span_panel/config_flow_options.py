"""Options flow helpers for Span Panel config flow."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry

from .const import (
    DEFAULT_SNAPSHOT_INTERVAL,
    ENABLE_CIRCUIT_NET_ENERGY_SENSORS,
    ENABLE_ENERGY_DIP_COMPENSATION,
    ENABLE_PANEL_NET_ENERGY_SENSORS,
    ENABLE_UNMAPPED_CIRCUIT_SENSORS,
    USE_CIRCUIT_NUMBERS,
    USE_DEVICE_PREFIX,
    EntityNamingPattern,
)
from .options import ENERGY_REPORTING_GRACE_PERIOD, SNAPSHOT_UPDATE_INTERVAL


def build_general_options_schema(
    config_entry: ConfigEntry,
    available_tabs: list[int] | None = None,
    current_leg1: int = 0,
    current_leg2: int = 0,
    user_input: dict[str, Any] | None = None,
) -> vol.Schema:
    """Build the schema for general options form.

    Args:
        config_entry: The config entry
        available_tabs: Unused (kept for backward compatibility)
        current_leg1: Unused (kept for backward compatibility)
        current_leg2: Unused (kept for backward compatibility)
        user_input: Current user input for dynamic updates

    Returns:
        Voluptuous schema for the form

    """
    schema_fields = {
        vol.Optional(SNAPSHOT_UPDATE_INTERVAL): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=15)
        ),
        vol.Optional(ENABLE_PANEL_NET_ENERGY_SENSORS): bool,
        vol.Optional(ENABLE_CIRCUIT_NET_ENERGY_SENSORS): bool,
        vol.Optional(ENABLE_UNMAPPED_CIRCUIT_SENSORS): bool,
        vol.Optional(ENERGY_REPORTING_GRACE_PERIOD): vol.All(
            int, vol.Range(min=0, max=60)
        ),
        vol.Optional(ENABLE_ENERGY_DIP_COMPENSATION): bool,
    }

    return vol.Schema(schema_fields)


def get_general_options_defaults(
    config_entry: ConfigEntry, current_leg1: int = 0, current_leg2: int = 0
) -> dict[str, Any]:
    """Get default values for general options form.

    Args:
        config_entry: The config entry
        current_leg1: Unused (kept for backward compatibility)
        current_leg2: Unused (kept for backward compatibility)

    Returns:
        Dictionary of default values

    """
    return {
        SNAPSHOT_UPDATE_INTERVAL: config_entry.options.get(
            SNAPSHOT_UPDATE_INTERVAL, DEFAULT_SNAPSHOT_INTERVAL
        ),
        ENABLE_PANEL_NET_ENERGY_SENSORS: config_entry.options.get(
            ENABLE_PANEL_NET_ENERGY_SENSORS, True
        ),
        ENABLE_CIRCUIT_NET_ENERGY_SENSORS: config_entry.options.get(
            ENABLE_CIRCUIT_NET_ENERGY_SENSORS, True
        ),
        ENABLE_UNMAPPED_CIRCUIT_SENSORS: config_entry.options.get(
            ENABLE_UNMAPPED_CIRCUIT_SENSORS, False
        ),
        ENERGY_REPORTING_GRACE_PERIOD: config_entry.options.get(
            ENERGY_REPORTING_GRACE_PERIOD, 15
        ),
        ENABLE_ENERGY_DIP_COMPENSATION: config_entry.options.get(
            ENABLE_ENERGY_DIP_COMPENSATION, False
        ),
    }


def process_general_options_input(
    config_entry: ConfigEntry,
    user_input: dict[str, Any],
    available_tabs: list[int] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    """Process user input for general options.

    Args:
        config_entry: The config entry
        user_input: User input from the form
        available_tabs: Unused (kept for backward compatibility)

    Returns:
        Tuple of (processed_options, errors)

    """
    errors: dict[str, str] = {}

    # Filter out separator fields from user input
    filtered_input = {
        k: v for k, v in user_input.items() if not k.startswith("_separator")
    }

    # Merge with existing options to preserve unchanged values
    merged_options = dict(config_entry.options)
    merged_options.update(filtered_input)
    filtered_input = merged_options

    # Preserve existing naming flags
    use_prefix = config_entry.options.get(USE_DEVICE_PREFIX, True)
    use_circuit_numbers = config_entry.options.get(USE_CIRCUIT_NUMBERS, False)
    filtered_input[USE_DEVICE_PREFIX] = use_prefix
    filtered_input[USE_CIRCUIT_NUMBERS] = use_circuit_numbers

    return filtered_input, errors


def get_current_naming_pattern(config_entry: ConfigEntry) -> str:
    """Determine the current entity naming pattern from configuration flags."""
    use_circuit_numbers = config_entry.options.get(USE_CIRCUIT_NUMBERS, False)
    use_device_prefix = config_entry.options.get(USE_DEVICE_PREFIX, False)

    if use_circuit_numbers:
        return EntityNamingPattern.CIRCUIT_NUMBERS.value
    if use_device_prefix:
        return EntityNamingPattern.FRIENDLY_NAMES.value
    return EntityNamingPattern.LEGACY_NAMES.value
