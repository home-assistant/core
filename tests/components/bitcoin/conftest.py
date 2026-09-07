"""Fixtures for the Bitcoin integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from blockchain.exchangerates import Currency
from blockchain.statistics import Stats
import pytest

from homeassistant.components.bitcoin.const import DOMAIN
from homeassistant.const import CONF_CURRENCY

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.bitcoin.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_statistics() -> Generator[MagicMock]:
    """Mock the blockchain.com network statistics."""
    with patch("homeassistant.components.bitcoin.sensor.statistics.get") as mock_get:
        mock_get.return_value = Stats(load_json_object_fixture("stats.json", DOMAIN))
        yield mock_get


@pytest.fixture
def mock_exchangerates() -> Generator[MagicMock]:
    """Mock the blockchain.com exchange rate ticker."""
    with patch(
        "homeassistant.components.bitcoin.sensor.exchangerates.get_ticker"
    ) as mock_get_ticker:
        mock_get_ticker.return_value = {
            "EUR": Currency(68512.4, 68515.9, 68508.9, "€", 68510.2),
            "USD": Currency(79618.09, 79622.5, 79613.7, "$", 79600.7),
        }
        yield mock_get_ticker


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock Bitcoin config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Bitcoin",
        data={CONF_CURRENCY: "USD"},
        entry_id="01JR3TZKNXVJ4S6ZKPD7A9BQ2E",
    )
