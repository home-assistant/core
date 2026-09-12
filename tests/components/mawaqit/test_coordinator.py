"""Tests for the Mawaqit coordinators."""

from datetime import timedelta

from mawaqit.exceptions import BadCredentialsException, MawaqitException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

# All shared data and setup are provided by conftest:
#   - mock_mosque_data, mock_prayer_data  ->  standard data dicts
#   - setup_mawaqit_integration           ->  async callable, see conftest docstring


# --- PrayerTimeCoordinator ---


async def test_prayer_time_coordinator_update_interval_is_12_hours(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
) -> None:
    """Test prayer time coordinator polls twice daily (12 hours)."""
    await setup_mawaqit_integration(
        mosque_data=mock_mosque_data, prayer_data=mock_prayer_data
    )
    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    assert coordinator.update_interval == timedelta(hours=12)


async def test_prayer_time_coordinator_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
) -> None:
    """Test successful prayer time fetch."""
    await setup_mawaqit_integration(
        mosque_data=mock_mosque_data, prayer_data=mock_prayer_data
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    assert coordinator.data == mock_prayer_data


@pytest.mark.parametrize(
    "prayer_side_effect",
    [ConnectionError, TimeoutError, MawaqitException],
)
async def test_prayer_time_coordinator_errors_cause_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
    prayer_side_effect: type[Exception],
) -> None:
    """Test prayer time coordinator non-auth errors all cause setup retry."""
    await setup_mawaqit_integration(
        mosque_data=mock_mosque_data, prayer_side_effect=prayer_side_effect
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_auth_error_causes_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test auth errors cause setup retry."""
    await setup_mawaqit_integration(prayer_side_effect=BadCredentialsException)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
) -> None:
    """Test prayer time coordinator with None prayer data causes setup retry."""
    await setup_mawaqit_integration(mosque_data=mock_mosque_data, prayer_data=None)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
