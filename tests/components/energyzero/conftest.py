"""Fixtures for EnergyZero integration tests."""

from collections.abc import AsyncGenerator, Generator
from datetime import UTC, date, datetime, tzinfo
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from zoneinfo import ZoneInfo

from energyzero import EnergyPrices, Interval, PriceType
from energyzero.models import REST_PRICE_STREAMS
import pytest

from homeassistant.components.energyzero.const import DOMAIN
from homeassistant.core import HomeAssistant

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

        def _get_prices(
            data: dict[str, Any],
            *,
            start_date: date,
            end_date: date | None = None,
            interval: Interval = Interval.QUARTER,
            price_type: PriceType | tuple[PriceType, ...] = PriceType.ALL_IN,
            local_tz: tzinfo | None = None,
        ) -> EnergyPrices | dict[PriceType, EnergyPrices]:
            local_tz = local_tz or ZoneInfo(hass.config.time_zone)
            requested_types = (
                (price_type,) if isinstance(price_type, PriceType) else price_type
            )
            results = {}
            for requested_type in requested_types:
                stream = REST_PRICE_STREAMS[requested_type]
                filtered_data = {
                    **data,
                    stream: [
                        item
                        for item in data[stream]
                        if datetime.strptime(item["start"], "%Y-%m-%dT%H:%M:%SZ")
                        .replace(tzinfo=UTC)
                        .astimezone(local_tz)
                        .date()
                        == start_date
                    ],
                }
                results[requested_type] = EnergyPrices.from_rest_dict(
                    filtered_data, requested_type
                )
            return results[price_type] if isinstance(price_type, PriceType) else results

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
