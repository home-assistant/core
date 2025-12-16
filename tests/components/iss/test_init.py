"""Test ISS integration setup."""

from unittest.mock import patch

import pytest

from homeassistant.components.iss.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            "show_on_map": False,
            "people_url": "http://api.open-notify.org/astros.json",
            "people_update_hours": 24,
            "position_update_seconds": 60,
        },
        unique_id="iss_test",
    )


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup of config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iss.coordinator.tle.IssTleCoordinator.async_config_entry_first_refresh"
        ) as mock_tle_refresh,
        patch(
            "homeassistant.components.iss.coordinator.position.IssPositionCoordinator.async_config_entry_first_refresh"
        ) as mock_position_refresh,
        patch(
            "homeassistant.components.iss.coordinator.people.IssPeopleCoordinator.async_config_entry_first_refresh"
        ) as mock_people_refresh,
    ):
        mock_tle_refresh.return_value = None
        mock_position_refresh.return_value = None
        mock_people_refresh.return_value = None

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN in hass.data
        assert mock_config_entry.entry_id in hass.data[DOMAIN]

        # Verify all coordinators are created
        coordinators = hass.data[DOMAIN][mock_config_entry.entry_id]
        assert "tle_coordinator" in coordinators
        assert "position_coordinator" in coordinators
        assert "people_coordinator" in coordinators


async def test_unload_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful unload of config entry."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.iss.coordinator.tle.IssTleCoordinator.async_config_entry_first_refresh"
        ),
        patch(
            "homeassistant.components.iss.coordinator.position.IssPositionCoordinator.async_config_entry_first_refresh"
        ),
        patch(
            "homeassistant.components.iss.coordinator.people.IssPeopleCoordinator.async_config_entry_first_refresh"
        ),
    ):
        # Setup first
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Then unload
        assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
        assert (
            DOMAIN not in hass.data
            or mock_config_entry.entry_id not in hass.data[DOMAIN]
        )


async def test_setup_entry_coordinator_failure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup failure when coordinator refresh fails."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.iss.coordinator.tle.IssTleCoordinator.async_config_entry_first_refresh",
        side_effect=Exception("TLE fetch failed"),
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
