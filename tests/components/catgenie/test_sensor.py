"""Test the CatGenie sensor platform."""

from unittest.mock import MagicMock

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from .conftest import MOCK_ENTRY_DATA

from tests.common import MockConfigEntry


async def test_sensors_created(
    hass: HomeAssistant,
    mock_catgenie_auth_init: MagicMock,
    mock_catgenie_client: MagicMock,
) -> None:
    """Test that sensor entities are created for each device."""
    entry = MockConfigEntry(
        domain="catgenie",
        data=MOCK_ENTRY_DATA,
        unique_id="test-user-id",
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    # Check key sensors exist
    state = hass.states.get("sensor.catgenie_litter_box_sani_solution_remaining")
    assert state is not None
    assert state.state == "75"

    state = hass.states.get("sensor.catgenie_litter_box_status")
    assert state is not None
    assert state.state == "cleaning"

    state = hass.states.get("sensor.catgenie_litter_box_clean_progress")
    assert state is not None
    assert state.state == "42"
