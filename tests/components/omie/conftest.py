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
    """Home Assistant configured for Madrid timezone."""
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


def price_enc(country: int, day: int, hour: int, minute: int) -> float:
    """Encodes the given data into a price.

    Format is CCDDhhmm000. Examples:
    -  351 15 01 15 000 for CC=351 (Portugal), DD=15 (day of month), hh=01 (1 am), mm=15.
    -   34 16 23 00 000 for CC=344 (Spain), DD=16 (day of month), hh=23 (11 pm), mm=00.

    This allows us to make assertions in tests without having
    to look up the expected values in large datasets.
    """
    return country * 10**9 + day * 10**7 + hour * 10**5 + minute * 10**3


@pytest.fixture
def mock_omie_results_jan15() -> OMIEResults:
    """Return mock OMIEResults for 2024-01-15."""
    test_date = dt.date(2024, 1, 15)
    spot_data = SpotData(
        url="https://example.com?date=2024-01-15",
        market_date=test_date.isoformat(),
        header="Test Data Jan 15",
        es_pt_total_power=[],
        es_purchases_power=[],
        pt_purchases_power=[],
        es_sales_power=[],
        pt_sales_power=[],
        es_pt_power=[],
        es_to_pt_exports_power=[],
        es_from_pt_imports_power=[],
        es_spot_price=[
            price_enc(country=34, day=15, hour=h, minute=m)
            for h in range(24)
            for m in (0, 15, 30, 45)
        ],
        pt_spot_price=[
            price_enc(country=351, day=15, hour=h, minute=m)
            for h in range(24)
            for m in (0, 15, 30, 45)
        ],
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
        es_pt_total_power=[],
        es_purchases_power=[],
        pt_purchases_power=[],
        es_sales_power=[],
        pt_sales_power=[],
        es_pt_power=[],
        es_to_pt_exports_power=[],
        es_from_pt_imports_power=[],
        es_spot_price=[
            price_enc(country=34, day=16, hour=h, minute=m)
            for h in range(24)
            for m in (0, 15, 30, 45)
        ],
        pt_spot_price=[
            price_enc(country=351, day=16, hour=h, minute=m)
            for h in range(24)
            for m in (0, 15, 30, 45)
        ],
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
