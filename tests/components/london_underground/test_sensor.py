"""The tests for the london_underground platform."""

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_valid_state(
    hass: HomeAssistant,
    mock_london_underground_client,
    mock_config_entry,
) -> None:
    """Test operational London Underground sensor using a mock config entry."""
    # Ensure the entry is fully loaded
    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Confirm that the expected entity exists and is correct
    state = hass.states.get("sensor.london_underground_metropolitan")
    assert state is not None
    assert state.state == "Good Service"
    assert state.attributes == {
        "Description": "Nothing to report",
        "attribution": "Powered by TfL Open Data",
        "friendly_name": "London Underground Metropolitan",
        "icon": "mdi:subway",
    }
