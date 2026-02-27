"""Tests for the Homevolt SELECT platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.homevolt.const import DOMAIN
from homeassistant.components.select import DOMAIN as SELECT_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, ATTR_OPTION, Platform
from homeassistant.core import HomeAssistant

# entity_registry is not required for these tests
from tests.common import MockConfigEntry


@pytest.fixture
def platforms_select() -> list[Platform]:
    """Return platforms including SELECT for this test."""
    # Sensor is required for the coordinator; add SELECT as well.
    return [Platform.SENSOR, Platform.SELECT]


async def test_select_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client,
    platforms_select: list[Platform],
) -> None:
    """The select entity should be created with correct options and state."""
    # Initialise integration with SELECT platform enabled.
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homevolt.PLATFORMS", platforms_select):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"select.{DOMAIN}_schedule_type"
    state = hass.states.get(entity_id)
    assert state is not None

    # The fixture schedule type is 1 → "grid_charge"
    assert state.state == "grid_charge"

    # Expect all defined schedule types to be present.
    expected_options = {
        "idle",
        "grid_charge",
        "grid_discharge",
        "solar_charge",
        "solar_discharge",
    }
    assert set(state.attributes["options"]) == expected_options


async def test_select_option_changes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homevolt_client,
    platforms_select: list[Platform],
) -> None:
    """Selecting a new option calls the client and triggers a refresh."""
    mock_config_entry.add_to_hass(hass)
    with patch("homeassistant.components.homevolt.PLATFORMS", platforms_select):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = f"select.{DOMAIN}_schedule_type"

    # Change to a different schedule type.
    await hass.services.async_call(
        SELECT_DOMAIN,
        "select_option",
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "solar_charge"},
        blocking=True,
    )

    # Verify the client method was called with the correct enum value (3).
    mock_homevolt_client.set_schedule_type.assert_awaited_once_with(3)

    # The coordinator should have refreshed the data.
    assert mock_homevolt_client.update_info.called
