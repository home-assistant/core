"""Integration tests for OMIE coordinator fetch behavior."""

from datetime import date
from unittest.mock import ANY, Mock, patch

from freezegun import freeze_time
import pytest

from homeassistant.components.omie.const import DOMAIN
from homeassistant.components.omie.coordinator import OMIECoordinator
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
async def hass_lisbon(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Lisbon")
    return hass


@pytest.fixture
def mock_pyomie():
    """Mock pyomie.spot_price with realistic responses."""
    with patch("homeassistant.components.omie.coordinator.pyomie") as mock:
        # Mock successful responses - return different mock objects for each call
        async def mock_spot_price(session, market_date):
            mock_result = Mock()
            mock_result.market_date = market_date
            mock_result.contents = Mock()
            mock_result.updated_at = Mock()
            return mock_result

        mock.spot_price.side_effect = mock_spot_price
        yield mock


@pytest.fixture
def mock_config_entry():
    """Mock config entry for OMIE integration."""
    return MockConfigEntry(domain=DOMAIN, data={}, title="OMIE Test")


@pytest.mark.asyncio
class TestOMIECoordinatorIntegration:
    """Integration tests for OMIE coordinator fetch behavior."""

    async def test_initial_setup_lisbon_timezone(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator fetches available data on initial setup (Lisbon timezone)."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # 4 PM Lisbon = 5 PM CET (after 13:30 CET publication)
        with freeze_time("2024-06-15 15:00:00"):  # 15:00 UTC = 16:00 Lisbon
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()

            # Should fetch both June 15 and June 16 (both published)
            assert mock_pyomie.spot_price.call_count == 2
            calls = [call.args[1] for call in mock_pyomie.spot_price.call_args_list]
            assert date(2024, 6, 15) in calls
            assert date(2024, 6, 16) in calls

    async def test_before_publication_lisbon_morning(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator doesn't fetch tomorrow's data before publication (Lisbon morning)."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # 12:20 PM Lisbon = 1:20 PM CET (before 1:30 PM CET publication for June 16)
        with freeze_time("2024-06-15 11:20:00"):  # 11:20 UTC = 12:20 Lisbon
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()

            # Should only fetch June 15, not June 16 (not yet published)
            assert mock_pyomie.spot_price.call_count == 1
            mock_pyomie.spot_price.assert_called_with(ANY, date(2024, 6, 15))

    async def test_no_redundant_fetches_different_times(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator doesn't refetch data at different times same day."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # First fetch at 3 PM Lisbon = 4 PM CET
        with freeze_time("2024-06-15 14:00:00"):  # 14:00 UTC = 15:00 Lisbon
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()
            first_call_count = mock_pyomie.spot_price.call_count

        # Second fetch at 8 PM Lisbon = 9 PM CET (much later same day)
        with freeze_time("2024-06-15 19:00:00"):  # 19:00 UTC = 20:00 Lisbon
            await coordinator.async_refresh()

            # Should not make additional calls - data still valid
            assert mock_pyomie.spot_price.call_count == first_call_count

    async def test_date_rollover_with_publication_timing(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator behavior during date rollover and publication timing."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # Start on June 15 after publication time
        with freeze_time("2024-06-15 14:00:00"):  # 14:00 UTC = 15:00 Lisbon = 4 PM CET
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()
            june15_calls = mock_pyomie.spot_price.call_count

        # Roll over to June 16 morning (before 13:30 CET publication)
        with freeze_time("2024-06-16 10:00:00"):  # 10:00 UTC = 11:00 Lisbon = 12 PM CET
            await coordinator.async_refresh()
            morning_calls = mock_pyomie.spot_price.call_count

            # Should not make additional calls - June 16 data was already fetched yesterday
            # June 17 data is not published yet
            assert morning_calls == june15_calls
            # Verify no additional calls were made
            assert len(mock_pyomie.spot_price.call_args_list) == june15_calls

        # Roll forward to after publication time same day
        with freeze_time("2024-06-16 14:00:00"):  # 14:00 UTC = 15:00 Lisbon = 4 PM CET
            await coordinator.async_refresh()

            # Now should fetch June 17 data (tomorrow, now published)
            final_calls = mock_pyomie.spot_price.call_count
            assert final_calls > morning_calls
            latest_call = mock_pyomie.spot_price.call_args_list[-1]
            assert latest_call.args[1] == date(2024, 6, 17)

    async def test_cross_publication_boundary(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator behavior crossing 13:30 CET publication boundary."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # Start just before publication time for June 16 data
        with freeze_time(
            "2024-06-15 11:25:00"
        ):  # 11:25 UTC = 12:25 Lisbon = 1:25 PM CET
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()
            pre_publication_calls = mock_pyomie.spot_price.call_count
            # Should only have June 15 data
            calls_before = [
                call.args[1] for call in mock_pyomie.spot_price.call_args_list
            ]
            assert date(2024, 6, 15) in calls_before
            assert date(2024, 6, 16) not in calls_before

        # Cross publication boundary (June 16 data now published)
        with freeze_time(
            "2024-06-15 11:35:00"
        ):  # 11:35 UTC = 12:35 Lisbon = 1:35 PM CET
            await coordinator.async_refresh()

            # Should now fetch tomorrow's data (June 16)
            post_publication_calls = mock_pyomie.spot_price.call_count
            assert post_publication_calls > pre_publication_calls
            latest_call = mock_pyomie.spot_price.call_args_list[-1]
            assert latest_call.args[1] == date(2024, 6, 16)

    async def test_weekend_publication_behavior(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator handles weekend publication correctly."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # Saturday morning before publication time
        with freeze_time("2024-06-15 10:00:00"):  # 10:00 UTC = 11:00 Lisbon = 12 PM CET
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()
            saturday_morning_calls = mock_pyomie.spot_price.call_count

        # Saturday afternoon after publication time
        with freeze_time("2024-06-15 14:00:00"):  # 14:00 UTC = 15:00 Lisbon = 4 PM CET
            await coordinator.async_refresh()

            # Should fetch Sunday's data (published Saturday at 13:30 CET)
            saturday_afternoon_calls = mock_pyomie.spot_price.call_count
            assert saturday_afternoon_calls > saturday_morning_calls
            latest_call = mock_pyomie.spot_price.call_args_list[-1]
            assert latest_call.args[1] == date(2024, 6, 16)  # Sunday

    async def test_data_persistence_across_refreshes(
        self, hass_lisbon, mock_config_entry, mock_pyomie
    ):
        """Test coordinator maintains data across refreshes without refetching."""
        mock_config_entry.add_to_hass(hass_lisbon)

        # Initial fetch
        with freeze_time("2024-06-15 14:00:00"):  # 14:00 UTC = 15:00 Lisbon = 4 PM CET
            coordinator = OMIECoordinator(hass_lisbon, mock_config_entry)
            await coordinator.async_refresh()

            # Verify data is stored
            assert coordinator.data is not None
            assert len(coordinator.data) > 0
            initial_data = coordinator.data.copy()
            initial_calls = mock_pyomie.spot_price.call_count

        # Multiple refreshes same day
        for hour in (16, 18, 20):  # 4 PM, 6 PM, 8 PM Lisbon
            with freeze_time(f"2024-06-15 {hour - 1:02d}:00:00"):  # UTC = Lisbon - 1
                await coordinator.async_refresh()

                # Data should remain the same, no additional calls
                assert coordinator.data == initial_data
                assert mock_pyomie.spot_price.call_count == initial_calls
