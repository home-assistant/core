"""Test the Roborock coordinator."""

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.VACUUM]


@pytest.mark.parametrize(
    ("map_present", "in_cleaning", "expected_reloads"),
    [
        # Idle vacuum reports no map loaded: reload the selected map once.
        (0, False, 1),
        # Never reload while the vacuum is cleaning.
        (0, True, 0),
        # Map is loaded: nothing to do.
        (1, False, 0),
    ],
)
async def test_reload_selected_map_when_missing(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    map_present: int,
    in_cleaning: bool,
    expected_reloads: int,
) -> None:
    """Test the selected map is reloaded once if the device has no map loaded."""
    if mock_roborock_entry.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_roborock_entry.runtime_data.v1[0]
    api = coordinator.properties_api
    api.maps.set_current_map.reset_mock()

    original_refresh = api.status.refresh.side_effect

    async def refresh_with_state() -> None:
        await original_refresh()
        api.status.map_present = map_present
        api.status.in_cleaning = in_cleaning

    api.status.refresh.side_effect = refresh_with_state

    # Refreshing twice must only trigger a single reload attempt.
    await coordinator.async_refresh()
    await coordinator.async_refresh()

    assert api.maps.set_current_map.await_count == expected_reloads
    if expected_reloads:
        api.maps.set_current_map.assert_awaited_with(api.maps.current_map)
