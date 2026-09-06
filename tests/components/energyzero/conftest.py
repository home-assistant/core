"""Fixtures for EnergyZero integration tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, PriceType
from energyzero.models import REST_PRICE_STREAMS
import pytest

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry, async_load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.energyzero.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="energy",
        domain=DOMAIN,
        data={},
        unique_id=DOMAIN,
        entry_id="12345",
    )


@pytest.fixture
async def mock_energyzero(hass: HomeAssistant) -> AsyncGenerator[MagicMock]:
    """Return a mocked EnergyZero client."""
    with patch(
        "homeassistant.components.energyzero.coordinator.EnergyZero", autospec=True
    ) as energyzero_mock:
        client = energyzero_mock.return_value
        energy_data = await async_load_json_object_fixture(
            hass, "today_energy.json", DOMAIN
        )
        gas_data = await async_load_json_object_fixture(hass, "today_gas.json", DOMAIN)

        def _get_prices(data: dict, *args, **kwargs) -> EnergyPrices:
            price_type = kwargs.get("price_type", args[0] if args else PriceType.ALL_IN)
            filter_date = kwargs.get("start_date", dt_util.now().date())
            local_tz = kwargs.get("local_tz", ZoneInfo(hass.config.time_zone))
            stream = REST_PRICE_STREAMS[price_type]
            filtered_data = {
                **data,
                stream: [
                    item
                    for item in data[stream]
                    if datetime.strptime(item["start"], "%Y-%m-%dT%H:%M:%SZ")
                    .replace(tzinfo=UTC)
                    .astimezone(local_tz)
                    .date()
                    == filter_date
                ],
            }
            return EnergyPrices.from_rest_dict(filtered_data, price_type)

        client.get_electricity_prices.side_effect = lambda *a, **kw: _get_prices(
            energy_data, *a, **kw
        )
        client.get_gas_prices.side_effect = lambda *a, **kw: _get_prices(
            gas_data, *a, **kw
        )
        yield client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_energyzero: MagicMock
) -> MockConfigEntry:
    """Set up the EnergyZero integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
