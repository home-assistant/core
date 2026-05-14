"""Common fixtures for the OMIE - Spain and Portugal electricity prices tests."""

from collections.abc import Generator
import datetime as dt
import json
from unittest.mock import AsyncMock, MagicMock, patch

from pyomie.model import OMIEResults, SpotData
import pytest

from homeassistant.components.omie.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import price_enc, spot_price_fetcher

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="OMIE",
        domain=DOMAIN,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.omie.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def hass_lisbon(hass: HomeAssistant) -> None:
    """Home Assistant configured for Lisbon timezone."""
    await hass.config.async_set_time_zone("Europe/Lisbon")


@pytest.fixture
async def hass_madrid(hass: HomeAssistant) -> None:
    """Home Assistant configured for Madrid timezone."""
    await hass.config.async_set_time_zone("Europe/Madrid")


@pytest.fixture
def mock_pyomie() -> Generator[MagicMock]:
    """Mock pyomie.spot_price with realistic responses."""
    with (
        patch("homeassistant.components.omie.coordinator.pyomie") as mock,
        patch("homeassistant.components.omie.config_flow.pyomie", mock),
    ):
        mock.spot_price.side_effect = spot_price_fetcher({})
        yield mock


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
