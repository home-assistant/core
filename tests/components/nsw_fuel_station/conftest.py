"""Common fixtures for the nsw_fuel_station tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from nsw_fuel import (
    FuelType,
    GetFuelPricesResponse,
    GetReferenceDataResponse,
    Price,
    Station,
)
import pytest

from homeassistant.components.nsw_fuel_station.const import (
    CONF_FUEL_TYPES,
    CONF_STATION_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="Joe's Station",
        domain=DOMAIN,
        data={
            CONF_STATION_ID: 222,
            CONF_FUEL_TYPES: ["E10", "DL"],
        },
        unique_id="12345",
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nsw_fuel_station.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


MOCK_STATIONS = [
    Station(
        id="devil1",
        brand="hot",
        code=666,
        name="Devil's Petrol Station",
        address="666 Roast St, Mortdale",
    ),
    Station(
        id="joe1",
        brand="joe",
        code=222,
        name="Joe's Servo",
        address="23 High St, Anytown",
    ),
    Station(
        id="bob1",
        brand="bob",
        code=333,
        name="Bob's Servo",
        address="34 Low St, Anytown",
    ),
]
MOCK_PRICES = [
    Price(
        fuel_type="E10",
        price=155.2,
        station_code=222,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="DL",
        price=165.5,
        station_code=222,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="P95",
        price=195.4,
        station_code=333,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="DL",
        price=192.3,
        station_code=333,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="E10",
        price=165.2,
        station_code=666,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="DL",
        price=265.1,
        station_code=666,
        last_updated=None,
        price_unit=None,
    ),
    Price(
        fuel_type="P95",
        price=223.2,
        station_code=666,
        last_updated=None,
        price_unit=None,
    ),
]


@pytest.fixture
def mock_fuelcheckclient() -> Generator[MagicMock]:
    """Return a mocked FuelCheckClient."""
    with (
        patch(
            "homeassistant.components.nsw_fuel_station.coordinator.FuelCheckClient",
            autospec=True,
        ) as fuelcheckclient_mock,
    ):
        fuelcheckclient = fuelcheckclient_mock.return_value
        fuelcheckclient.get_fuel_prices.return_value = GetFuelPricesResponse(
            stations=MOCK_STATIONS,
            prices=MOCK_PRICES,
        )
        fuelcheckclient.get_reference_data.return_value = GetReferenceDataResponse(
            stations=None,
            brands=None,
            trend_periods=None,
            sort_fields=None,
            fuel_types=[
                FuelType(code="E10", name="E10 Unleaded"),
                FuelType(code="P95", name="Premium 95"),
                FuelType(code="DL", name="Diesel"),
            ],
        )
        yield fuelcheckclient


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_fuelcheckclient: MagicMock,
) -> MockConfigEntry:
    """Set up the NSW Fuel Station integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
