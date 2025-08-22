"""Test coordinator utility functions for OMIE integration."""

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

from freezegun import freeze_time
from pyomie.model import OMIEResults, SpotData
import pytest

from homeassistant.components.omie.const import DOMAIN
from homeassistant.components.omie.coordinator import OMIECoordinator
from homeassistant.components.omie.util import _get_market_dates, _is_published
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

UTC = ZoneInfo("UTC")


class TestIntegrationScenarios:
    """Test _get_market_dates and _is_published together."""

    def test_lisbon_user_typical_day(self) -> None:
        """Test typical day for Portuguese user."""
        tz = ZoneInfo("Europe/Lisbon")
        local_time = datetime(2024, 6, 15, 15, 0, tzinfo=tz)  # 3 PM local

        # Get market dates needed
        market_dates = _get_market_dates(tz, local_time)

        # Check which are published
        published_dates = {d for d in market_dates if _is_published(d, local_time)}

        # At 3 PM on June 15, both dates should be published (after 13:30 CET for both)
        assert market_dates == {date(2024, 6, 15), date(2024, 6, 16)}
        assert published_dates == {date(2024, 6, 15), date(2024, 6, 16)}

    def test_madrid_user_early_morning(self) -> None:
        """Test early morning scenario for Spanish user."""
        tz = ZoneInfo("Europe/Madrid")
        local_time = datetime(2024, 6, 15, 8, 0, tzinfo=tz)  # 8 AM local = 8 AM CET

        market_dates = _get_market_dates(tz, local_time)
        published_dates = {d for d in market_dates if _is_published(d, local_time)}

        # At 8 AM on June 15, only June 15 data should be published
        # June 16 data publishes at 13:30 CET on June 15 (not yet)
        assert market_dates == {date(2024, 6, 15)}
        assert published_dates == {date(2024, 6, 15)}


@pytest.fixture
def mock_omie_results_jan15():
    """Return mock OMIEResults for 2024-01-15."""
    test_date = date(2024, 1, 15)
    spot_data = SpotData(
        url="https://example.com?date=2024-01-15",
        market_date=test_date.isoformat(),
        header="Test Data Jan 15",
        energy_total_es_pt=[],
        energy_purchases_es=[],
        energy_purchases_pt=[],
        energy_sales_es=[],
        energy_sales_pt=[],
        energy_es_pt=[],
        energy_export_es_to_pt=[],
        energy_import_es_from_pt=[],
        spot_price_es=[47.1, 44.2, 41.5, 39.9, 38.8, 38.1]
        + [0.0] * 18,  # 6 hours + padding
        spot_price_pt=[45.5, 42.3, 39.8, 38.2, 37.5, 36.9]
        + [0.0] * 18,  # 6 hours + padding
    )
    return OMIEResults(
        updated_at=datetime.now(),
        market_date=test_date,
        contents=spot_data,
        raw=json.dumps(spot_data),
    )


@pytest.fixture
def mock_omie_results_jan16():
    """Return mock OMIEResults for 2024-01-16."""
    test_date = date(2024, 1, 16)
    spot_data = SpotData(
        url="https://example.com?date=2024-01-16",
        market_date=test_date.isoformat(),
        header="Test Data Jan 16",
        energy_total_es_pt=[],
        energy_purchases_es=[],
        energy_purchases_pt=[],
        energy_sales_es=[],
        energy_sales_pt=[],
        energy_es_pt=[],
        energy_export_es_to_pt=[],
        energy_import_es_from_pt=[],
        spot_price_es=[52.3, 49.1, 46.2, 43.8, 42.1, 41.0]
        + [0.0] * 18,  # 6 hours + padding
        spot_price_pt=[50.1, 47.8, 44.9, 42.4, 40.7, 39.2]
        + [0.0] * 18,  # 6 hours + padding
    )
    return OMIEResults(
        updated_at=datetime.now(),
        market_date=test_date,
        contents=spot_data,
        raw=json.dumps(spot_data),
    )


@pytest.fixture
def mock_config_entry():
    """Return mock config entry for coordinator testing."""
    return MockConfigEntry(
        title="OMIE",
        domain=DOMAIN,
        unique_id="omie_singleton",
    )


def spot_price_fetcher_factory(spot_price_data: dict):
    """Return spot price fetcher for any data dictionary.

    Args:
        spot_price_data: Dictionary mapping ISO date strings to mock results
    """
    data_by_date = {
        date.fromisoformat(iso_date): mock_result
        for iso_date, mock_result in spot_price_data.items()
    }

    async def spot_price_fetcher(session, requested_date):
        return data_by_date.get(requested_date)

    return spot_price_fetcher


class TestOMIECoordinatorDataMapping:
    """Test OMIECoordinator data mapping functionality."""

    @freeze_time("2024-01-15 15:00:00")
    async def test_single_date_mapping(
        self,
        hass_madrid: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_omie_results_jan15,
    ) -> None:
        """Test that coordinator correctly maps single date data."""

        coordinator = OMIECoordinator(
            hass_madrid,
            mock_config_entry,
            spot_price_fetcher=spot_price_fetcher_factory(
                {"2024-01-15": mock_omie_results_jan15}
            ),
        )

        # Call _async_update_data
        result = await coordinator._async_update_data()

        # Verify the result is correctly mapped by date
        expected = {date(2024, 1, 15): mock_omie_results_jan15}
        assert result == expected

    @freeze_time("2024-01-15 15:00:00")
    async def test_multiple_dates_mapping(
        self,
        hass_lisbon: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_omie_results_jan15,
        mock_omie_results_jan16,
    ) -> None:
        """Test that coordinator correctly maps data for multiple API calls."""

        # Test scenario 1: Jan 15
        spot_price_fetcher = spot_price_fetcher_factory(
            {
                "2024-01-15": mock_omie_results_jan15,
                "2024-01-16": mock_omie_results_jan16,
            }
        )

        coordinator = OMIECoordinator(
            hass_lisbon,
            mock_config_entry,
            spot_price_fetcher=spot_price_fetcher,
        )

        result = await coordinator._async_update_data()
        assert result == {
            date(2024, 1, 15): mock_omie_results_jan15,
            date(2024, 1, 16): mock_omie_results_jan16,
        }

    async def test_data_persistence(
        self,
        hass_madrid: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_omie_results_jan15,
        mock_omie_results_jan16,
    ) -> None:
        """Test that data persists appropriately and only for relevant dates."""
        spot_price_fetcher = spot_price_fetcher_factory(
            {
                "2024-01-15": mock_omie_results_jan15,
                "2024-01-16": mock_omie_results_jan16,
            }
        )

        # Test scenario 1: First call at Jan 15 evening
        with freeze_time("2024-01-15 20:30:00"):
            coordinator = OMIECoordinator(
                hass_madrid,
                mock_config_entry,
                spot_price_fetcher=spot_price_fetcher,
            )

            await coordinator.async_refresh()
            assert coordinator.data == {
                date(2024, 1, 15): mock_omie_results_jan15,
            }

            # call again --- next day
            with freeze_time("2024-01-16 15:00:00"):
                await coordinator.async_refresh()
                assert coordinator.data == {
                    date(2024, 1, 16): mock_omie_results_jan16,
                }

    @freeze_time("2024-01-15 15:00:00")
    async def test_none_response_handling(
        self,
        hass_madrid: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ) -> None:
        """Test that coordinator handles None responses from pyomie gracefully."""

        coordinator = OMIECoordinator(
            hass_madrid,
            mock_config_entry,
            spot_price_fetcher=spot_price_fetcher_factory({}),
        )

        # Call _async_update_data
        result = await coordinator._async_update_data()

        # Should return empty dict when no data is available
        assert result == {}

    @freeze_time("2024-01-15 23:30:00")
    async def test_date_key_correctness(
        self,
        hass_lisbon: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        mock_omie_results_jan15,
        mock_omie_results_jan16,
    ) -> None:
        """Test that the date key matches the requested date for the API call."""

        coordinator = OMIECoordinator(
            hass_lisbon,
            mock_config_entry,
            spot_price_fetcher=spot_price_fetcher_factory(
                {
                    "2024-01-15": mock_omie_results_jan15,
                    "2024-01-16": mock_omie_results_jan16,
                }
            ),
        )

        result = await coordinator._async_update_data()

        # Verify that dates are correctly mapped by the coordinator
        assert result == {
            date(2024, 1, 15): mock_omie_results_jan15,
            date(2024, 1, 16): mock_omie_results_jan16,
        }
