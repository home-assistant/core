"""Tests for the Control4 integration."""

from typing import Any
from unittest.mock import MagicMock

from pytest_homeassistant.common import MockConfigEntry

from homeassistant.core import HomeAssistant


def mock_director_variables(
    mock_c4_director: MagicMock, variables: dict[int, dict[str, Any]]
) -> None:
    """Make the director report the given variables, as pyControl4 returns them."""

    def get_all_item_variable_value(variable_names: set[str]) -> list[dict[str, Any]]:
        response = [
            {"id": item_id, "varName": name, "value": value}
            for item_id, item_variables in variables.items()
            for name, value in item_variables.items()
            if name in variable_names
        ]
        if not response:
            # pyControl4 raises ValueError when no item has any of the variables.
            raise ValueError("Empty response received from Director!")
        return response

    mock_c4_director.get_all_item_variable_value.side_effect = (
        get_all_item_variable_value
    )


async def setup_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the Control4 integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
