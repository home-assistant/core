"""Fixture definitions for NSW Fuel UI tests."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from nsw_fuel.dto import Price, Station, StationPrice
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
)

from nsw_fuel.const import DOMAIN

LATITUDE = -35.28
LONGITUDE = 149.13
HOME_LAT = -35.28
HOME_LNG = 149.13
HOBART_LAT = -42.88
HOBART_LNG = 147.32
STATION_NSW_A = 111
STATION_NSW_B = 222
STATION_NSW_C = 444
STATION_TAS_D = 333
STATION_TAS_E = 555
CLIENT_ID = "test_client_id"
CLIENT_SECRET = "test_client_secret"  # noqa: S105

STATIONS_NSW = [
    {
        "station_code": STATION_NSW_A,
        "station_name": "Ampol Foodary Ampol Foodary Batemans Bay",
        "au_state": "NSW",
    },
    {
        "station_code": STATION_NSW_B,
        "station_name": "Ultra Petroleum Ultra Mogo",
        "au_state": "NSW",
    },
    {
        "station_code": STATION_NSW_C,
        "station_name": "Shell Merimbula",
        "au_state": "NSW",
    },
]

STATIONS_TAS = [
    {"station_code": STATION_TAS_D, "station_name": "United Burnie", "au_state": "TAS"},
    {
        "station_code": STATION_TAS_E,
        "station_name": "Caltex Launceston",
        "au_state": "TAS",
    },
]

FUEL_PRICES = {
    STATION_NSW_A: {
        "U91": 170.5,
        "E10": 165.3,
        "DL": 180.1,
    },
    STATION_NSW_B: {
        "U91": 172.0,
        "E10": 167.0,
    },
    STATION_NSW_C: {
        "U91": 168.9,
        "E10": 163.5,
        "DL": 178.2,
    },
    STATION_TAS_D: {
        "U91": 175.0,
    },
    STATION_TAS_E: {
        "U91": 176.5,
        "DL": 185.3,
    },
}


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations) -> None:
    yield


@pytest.fixture(name="mock_api_client")
def mock_api_client_fixture():
    """Return a mock of the NSWFuelApi client."""
    client = MagicMock()

    client.authenticate = AsyncMock(return_value=True)

    async def _get_stations_near_location(
        latitude: float, longitude: float, radius: int = 25
    ):
        if latitude < -40:
            return STATIONS_TAS
        return STATIONS_NSW

    client.get_stations_near_location = AsyncMock(
        side_effect=_get_stations_near_location
    )

    async def _get_fuel_prices_for_station(station_code: str, au_state: str = "NSW"):
        """Return List[Price] (favorites path)."""
        station_code = int(station_code)
        station_prices = FUEL_PRICES.get(station_code, {})

        return [
            Price(
                fuel_type=fuel_type,
                price=price,
                last_updated="2024-01-01T00:00:00Z",
                price_unit="c/L",
                station_code=station_code,
            )
            for fuel_type, price in station_prices.items()
        ]

    client.get_fuel_prices_for_station = AsyncMock(
        side_effect=_get_fuel_prices_for_station
    )

    async def _get_fuel_prices_within_radius(
        latitude: float, longitude: float, radius: int = 25, fuel_type: str = "U91"
    ):
        stations = await _get_stations_near_location(latitude, longitude, radius)
        results = []

        for station_data in stations:
            station_code = station_data["station_code"]
            station_prices = FUEL_PRICES.get(station_code, {})

            for fuel, price_value in station_prices.items():
                if fuel_type and fuel != fuel_type:
                    continue

                station = Station(
                    ident=None,
                    brand="Test Brand",
                    code=station_code,
                    name=station_data["station_name"],
                    address="Test Address",
                    latitude=latitude,
                    longitude=longitude,
                    au_state=station_data["au_state"],
                )

                price = Price(
                    fuel_type=fuel,
                    price=price_value,
                    last_updated="2024-01-01T00:00:00Z",
                    price_unit="c/L",
                    station_code=station_code,
                )

                results.append(StationPrice(station=station, price=price))

        return results

    client.get_fuel_prices_within_radius = AsyncMock(
        side_effect=_get_fuel_prices_within_radius
    )

    return client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Fixture for creating a mock NSW Fuel config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "nicknames": {
                "Home": {
                    "stations": [
                        {
                            "station_code": STATION_NSW_A,
                            "au_state": "NSW",
                            "fuel_types": ["U91", "E10"],
                        }
                    ]
                }
            }
        },
        entry_id="test",
        version=1,
        unique_id="test-unique-id",
        title="NSW Fuel Check",
    )


@pytest.fixture
def mock_env() -> dict[str, str]:
    """Fixture providing mock environment variables for NSW Fuel API."""
    return {
        "NSW_FUEL_CLIENT_ID": "test_client_id",
        "NSW_FUEL_CLIENT_SECRET": "test_client_secret",
    }
