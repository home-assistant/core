"""Test the Roborock coordinator."""

from collections.abc import Generator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from roborock.exceptions import RoborockException

from homeassistant.components.roborock.const import MAP_SLEEP
from homeassistant.components.roborock.coordinator import RoborockDataUpdateCoordinator
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.VACUUM]


@pytest.fixture(autouse=True)
def mock_coordinator_sleep() -> Generator[AsyncMock]:
    """Mock asyncio_sleep in coordinator to avoid test delays."""
    with patch(
        "homeassistant.components.roborock.coordinator.asyncio_sleep",
        new_callable=AsyncMock,
    ) as mock:
        yield mock


async def _async_update(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    coordinator: RoborockDataUpdateCoordinator,
) -> None:
    """Advance time so the coordinator runs its scheduled update."""
    assert coordinator.update_interval is not None
    freezer.tick(coordinator.update_interval + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


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
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
    mock_coordinator_sleep: AsyncMock,
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
    await _async_update(hass, freezer, coordinator)
    await _async_update(hass, freezer, coordinator)

    assert api.maps.set_current_map.await_count == expected_reloads
    if expected_reloads:
        api.maps.set_current_map.assert_awaited_with(api.maps.current_map)
        mock_coordinator_sleep.assert_awaited_with(MAP_SLEEP)


async def test_reload_selected_map_waits_before_refresh(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
    mock_coordinator_sleep: AsyncMock,
) -> None:
    """Test waiting MAP_SLEEP seconds before updating map after reloading selected map."""
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
        api.status.map_present = 0
        api.status.in_cleaning = False

    api.status.refresh.side_effect = refresh_with_state

    call_order: list[str] = []

    async def mock_set_current_map(*args: Any, **kwargs: Any) -> None:
        call_order.append("set_current_map")

    async def mock_sleep(seconds: float) -> None:
        call_order.append(f"sleep_{seconds}")

    async def mock_update_map() -> None:
        call_order.append("update_map")

    api.maps.set_current_map.side_effect = mock_set_current_map
    mock_coordinator_sleep.side_effect = mock_sleep

    with patch.object(coordinator, "update_map", side_effect=mock_update_map):
        await _async_update(hass, freezer, coordinator)

    assert call_order == ["set_current_map", f"sleep_{MAP_SLEEP}", "update_map"]


async def test_reload_selected_map_subsequent_missing_episode(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test subsequent missing-map episode triggers another reload."""
    if mock_roborock_entry.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_roborock_entry.runtime_data.v1[0]
    api = coordinator.properties_api
    api.maps.set_current_map.reset_mock()

    current_map_present = 0
    current_in_cleaning = False

    original_refresh = api.status.refresh.side_effect

    async def refresh_with_state() -> None:
        await original_refresh()
        api.status.map_present = current_map_present
        api.status.in_cleaning = current_in_cleaning

    api.status.refresh.side_effect = refresh_with_state

    # First episode: idle with no map loaded triggers reload.
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1
    assert coordinator._map_reload_attempted is True

    # Refresh again in same state: should not reload again.
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1

    # Map becomes available while idle, resetting reload state.
    current_map_present = 1
    current_in_cleaning = False
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1
    assert coordinator._map_reload_attempted is False

    # Second episode: map is missing again, triggering another reload.
    current_map_present = 0
    current_in_cleaning = False
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 2
    assert coordinator._map_reload_attempted is True

    # Refresh again in same state: should not reload again.
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 2


async def test_reload_selected_map_available_during_cleaning(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test map becoming available during cleaning resets reload attempt state."""
    if mock_roborock_entry.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_roborock_entry.runtime_data.v1[0]
    api = coordinator.properties_api
    api.maps.set_current_map.reset_mock()

    current_map_present = 0
    current_in_cleaning = False

    original_refresh = api.status.refresh.side_effect

    async def refresh_with_state() -> None:
        await original_refresh()
        api.status.map_present = current_map_present
        api.status.in_cleaning = current_in_cleaning

    api.status.refresh.side_effect = refresh_with_state

    # Initial episode: idle missing map triggers reload.
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1
    assert coordinator._map_reload_attempted is True

    # Map becomes available during cleaning.
    current_map_present = 1
    current_in_cleaning = True
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1
    assert coordinator._map_reload_attempted is False

    # Still cleaning, but map is lost: must not reload while cleaning.
    current_map_present = 0
    current_in_cleaning = True
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 1
    assert coordinator._map_reload_attempted is False

    # Cleaning finishes and vacuum is idle with map still missing: triggers reload.
    current_map_present = 0
    current_in_cleaning = False
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 2
    assert coordinator._map_reload_attempted is True

    # Refresh again in same state: should not reload again.
    await _async_update(hass, freezer, coordinator)
    assert api.maps.set_current_map.await_count == 2


@pytest.mark.parametrize(
    ("set_map_error", "update_map_error", "expected_update_calls"),
    [
        (RoborockException("boom"), None, 0),
        (None, HomeAssistantError("boom"), 1),
        (None, RoborockException("boom"), 1),
    ],
)
async def test_reload_selected_map_failure_is_handled(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
    set_map_error: Exception | None,
    update_map_error: Exception | None,
    expected_update_calls: int,
) -> None:
    """Test a failing map reload does not break the coordinator update."""
    if mock_roborock_entry.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_roborock_entry.runtime_data.v1[0]
    api = coordinator.properties_api
    api.maps.set_current_map.reset_mock()
    api.maps.set_current_map.side_effect = set_map_error

    original_refresh = api.status.refresh.side_effect

    async def refresh_with_state() -> None:
        await original_refresh()
        api.status.map_present = 0
        api.status.in_cleaning = False

    api.status.refresh.side_effect = refresh_with_state

    with patch.object(
        coordinator, "update_map", side_effect=update_map_error
    ) as mock_update_map:
        await _async_update(hass, freezer, coordinator)

    assert api.maps.set_current_map.await_count == 1
    assert mock_update_map.await_count == expected_update_calls


async def test_reload_selected_map_skipped_without_current_map(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_roborock_entry: MockConfigEntry,
) -> None:
    """Test no reload is attempted when no map is selected."""
    if mock_roborock_entry.state is not ConfigEntryState.LOADED:
        await hass.config_entries.async_setup(mock_roborock_entry.entry_id)
        await hass.async_block_till_done()
    assert mock_roborock_entry.state is ConfigEntryState.LOADED

    coordinator = mock_roborock_entry.runtime_data.v1[0]
    api = coordinator.properties_api
    api.maps.set_current_map.reset_mock()
    api.maps.current_map = None

    original_refresh = api.status.refresh.side_effect

    async def refresh_with_state() -> None:
        await original_refresh()
        api.status.map_present = 0
        api.status.in_cleaning = False

    api.status.refresh.side_effect = refresh_with_state

    await _async_update(hass, freezer, coordinator)

    api.maps.set_current_map.assert_not_awaited()
