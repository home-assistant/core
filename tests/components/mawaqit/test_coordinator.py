"""Tests for the Mawaqit coordinators."""

from datetime import timedelta
from unittest.mock import AsyncMock, patch

from mawaqit.consts import BadCredentialsException, NoMosqueAround, NoMosqueFound

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry


async def _setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mosque_data: dict | None = None,
    prayer_data: dict | None = None,
    mosque_side_effect: Exception | None = None,
    prayer_side_effect: Exception | None = None,
) -> None:
    """Set up a config entry with optional mocked data or side effects."""
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
            side_effect=mosque_side_effect,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new_callable=AsyncMock,
            return_value=prayer_data,
            side_effect=prayer_side_effect,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()


# --- MosqueCoordinator ---


async def test_mosque_coordinator_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful mosque data fetch."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    await _setup_entry(
        hass, mock_config_entry, mosque_data=mosque_data, prayer_data=prayer_data
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data.mosque_coordinator.data == mosque_data


async def test_mosque_coordinator_bad_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator with bad credentials causes setup retry."""
    await _setup_entry(
        hass, mock_config_entry, mosque_side_effect=BadCredentialsException
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_no_mosque(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator when no mosque found causes setup retry."""
    await _setup_entry(hass, mock_config_entry, mosque_side_effect=NoMosqueAround)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_no_mosque_found(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator when NoMosqueFound causes setup retry."""
    await _setup_entry(hass, mock_config_entry, mosque_side_effect=NoMosqueFound)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator with connection error causes setup retry."""
    await _setup_entry(hass, mock_config_entry, mosque_side_effect=ConnectionError)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_timeout_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator with timeout error causes setup retry."""
    await _setup_entry(hass, mock_config_entry, mosque_side_effect=TimeoutError)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_mosque_coordinator_empty_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test mosque coordinator with empty data causes setup retry."""
    await _setup_entry(hass, mock_config_entry, mosque_data=None)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


# --- PrayerTimeCoordinator ---


async def test_prayer_time_coordinator_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful prayer time fetch."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    await _setup_entry(
        hass, mock_config_entry, mosque_data=mosque_data, prayer_data=prayer_data
    )
    assert mock_config_entry.state is ConfigEntryState.LOADED
    coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
    assert coordinator.data == prayer_data
    assert coordinator.last_fetch is not None
    assert coordinator.prayer_times == prayer_data


async def test_prayer_time_coordinator_cached(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator uses cached data within 1 day."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    mock_fetch = AsyncMock(return_value=prayer_data)

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
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
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator re-fetches after more than 1 day."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    prayer_data = {"calendar": [{}], "timezone": "Europe/Paris"}

    mock_fetch = AsyncMock(return_value=prayer_data)

    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_mosque_by_id",
            new_callable=AsyncMock,
            return_value=mosque_data,
        ),
        patch(
            "homeassistant.components.mawaqit.mawaqit_wrapper.fetch_prayer_times",
            new=mock_fetch,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Simulate time passing beyond 1 day
        coordinator = mock_config_entry.runtime_data.prayer_time_coordinator
        coordinator.last_fetch = dt_util.utcnow() - timedelta(days=2)
        await coordinator.async_refresh()

    assert mock_fetch.call_count == 2


async def test_prayer_time_coordinator_bad_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator with bad credentials causes setup retry."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_entry(
        hass,
        mock_config_entry,
        mosque_data=mosque_data,
        prayer_side_effect=BadCredentialsException,
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_no_mosque(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator when no mosque found causes setup retry."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_entry(
        hass,
        mock_config_entry,
        mosque_data=mosque_data,
        prayer_side_effect=NoMosqueAround,
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_connection_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator with connection error causes setup retry."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_entry(
        hass,
        mock_config_entry,
        mosque_data=mosque_data,
        prayer_side_effect=ConnectionError,
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_timeout_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator with timeout error causes setup retry."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_entry(
        hass,
        mock_config_entry,
        mosque_data=mosque_data,
        prayer_side_effect=TimeoutError,
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_prayer_time_coordinator_empty_data(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test prayer time coordinator with empty data causes setup retry."""
    mosque_data = {"name": "Test Mosque", "uuid": "abc"}
    await _setup_entry(
        hass, mock_config_entry, mosque_data=mosque_data, prayer_data=None
    )
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
