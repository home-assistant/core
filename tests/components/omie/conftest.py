"""Common fixtures for the OMIE - Spain and Portugal electricity prices tests."""

from collections.abc import Generator
import datetime as dt
from datetime import date
import json
from unittest.mock import AsyncMock, Mock, patch

from pyomie.model import OMIEResults, SpotData
import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.omie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def hass_lisbon(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Lisbon")
    return hass


@pytest.fixture
async def hass_madrid(hass: HomeAssistant):
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Madrid")
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
def mock_omie_results_jan15() -> OMIEResults:
    """Return mock OMIEResults for 2024-01-15."""
    test_date = dt.date(2024, 1, 15)
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
        # format: 34.DDhh for ES
        # format: 351.DDhh for PT
        spot_price_es=[1000 * (34 + 15 / 100 + h / 10000) for h in range(24)],
        spot_price_pt=[1000 * (351 + 15 / 100 + h / 10000) for h in range(24)],
    )
    return OMIEResults(
        updated_at=dt.datetime.now(),
        market_date=test_date,
        contents=spot_data,
        raw=json.dumps(spot_data),
    )


@pytest.fixture
def mock_omie_results_jan16() -> OMIEResults:
    """Return mock OMIEResults for 2024-01-16."""
    test_date = dt.date(2024, 1, 16)
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
        # format: 34.DDhh for ES
        # format: 351.DDhh for PT
        spot_price_es=[1000 * (34 + 16 / 100 + h / 10000) for h in range(24)],
        spot_price_pt=[1000 * (351 + 16 / 100 + h / 10000) for h in range(24)],
    )
    return OMIEResults(
        updated_at=dt.datetime.now(),
        market_date=test_date,
        contents=spot_data,
        raw=json.dumps(spot_data),
    )


def spot_price_fetcher(spot_price_data: dict):
    """Return spot price fetcher for any data dictionary.

    Args:
        spot_price_data: Dictionary mapping ISO date strings to mock results
    """
    data_by_date = {
        date.fromisoformat(iso_date): mock_result
        for iso_date, mock_result in spot_price_data.items()
    }

    async def spot_price_fetcher_(session, requested_date) -> OMIEResults:
        return data_by_date.get(requested_date)

    return spot_price_fetcher_
