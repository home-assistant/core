"""Tests for the Mawaqit coordinators."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from mawaqit.exceptions import BadCredentialsException, MawaqitException
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry

# All shared data and setup are provided by conftest:
#   - mock_mosque_data, mock_prayer_data  ->  standard data dicts
#   - setup_mawaqit_integration           ->  async callable, see conftest docstring


# --- MosqueCoordinator ---


async def test_mosque_coordinator_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
) -> None:
    """Test successful mosque data fetch."""
    await setup_mawaqit_integration(
        mosque_data=mock_mosque_data, prayer_data=mock_prayer_data
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.mosque_coordinator.data == mock_mosque_data


@pytest.mark.parametrize(
    "mosque_side_effect",
    [ConnectionError, TimeoutError, MawaqitException],
)
async def test_mosque_coordinator_errors_cause_setup_retry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mosque_side_effect: type[Exception],
) -> None:
    """Test mosque coordinator non-auth errors all cause setup retry."""
    await setup_mawaqit_integration(mosque_side_effect=mosque_side_effect)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test auth errors trigger reauthentication."""
    await setup_mawaqit_integration(mosque_side_effect=BadCredentialsException)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    # ConfigEntryAuthFailed triggers a reauth flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_mosque_coordinator_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test mosque coordinator with None mosque data causes setup retry."""
    # Explicitly passing mosque_data=None tells the helper to inject None
    # as the mock return value (coordinator receives no data -> UpdateFailed).
    await setup_mawaqit_integration(mosque_data=None)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


# --- PrayerTimeCoordinator ---


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
    assert coordinator.last_fetch is not None


async def test_prayer_time_coordinator_cached(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
) -> None:
    """Test prayer time coordinator uses cached data within 12 hours."""
    mock_fetch = AsyncMock(return_value=mock_prayer_data)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mock_mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new=mock_fetch,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        # Call refresh again - should use cache
        coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
        await coordinator.async_refresh()

    assert mock_fetch.call_count == 1


async def test_prayer_time_coordinator_refresh_after_day(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_mosque_data: dict,
    mock_prayer_data: dict,
) -> None:
    """Test prayer time coordinator re-fetches after more than 12 hours."""
    mock_fetch = AsyncMock(return_value=mock_prayer_data)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mock_mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new=mock_fetch,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
        coordinator.last_fetch = dt_util.utcnow() - timedelta(days=2)
        await coordinator.async_refresh()

    assert mock_fetch.call_count == 2


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


async def test_prayer_time_coordinator_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
) -> None:
    """Test auth errors trigger reauthentication."""
    await setup_mawaqit_integration(prayer_side_effect=BadCredentialsException)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    # ConfigEntryAuthFailed triggers a reauth flow
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["step_id"] == "reauth_confirm"


async def test_prayer_time_coordinator_empty_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    setup_mawaqit_integration,
    mock_mosque_data: dict,
) -> None:
    """Test prayer time coordinator with None prayer data causes setup retry."""
    await setup_mawaqit_integration(mosque_data=mock_mosque_data, prayer_data=None)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
