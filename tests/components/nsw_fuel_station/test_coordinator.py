"""Tests for NSWFuelCoordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from nsw_tas_fuel import (
    NSWFuelApiClientAuthError,
    NSWFuelApiClientError,
    Price,
    Station,
    StationPrice,
)
import pytest

from homeassistant.components.nsw_fuel_station.const import DEFAULT_FUEL_TYPE
from homeassistant.components.nsw_fuel_station.coordinator import NSWFuelCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import HOBART_LAT, HOBART_LNG, HOME_LAT, HOME_LNG, STATION_NSW_A


@pytest.fixture
def nicknames_home_only() -> dict:
    """Single NSW nickname."""
    return {
        "Home": {
            "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
            "stations": [
                {
                    "station_code": STATION_NSW_A,
                    "au_state": "NSW",
                    "fuel_types": ["U91", "E10"],
                }
            ],
        }
    }


@pytest.fixture
def nicknames_home_and_hobart() -> dict:
    """NSW + TAS nicknames."""
    return {
        "Home": {
            "location": {"latitude": HOME_LAT, "longitude": HOME_LNG},
            "stations": [],
        },
        "Hobart": {
            "location": {"latitude": HOBART_LAT, "longitude": HOBART_LNG},
            "stations": [],
        },
    }


@pytest.fixture
def coordinator(
    hass: HomeAssistant, mock_api_client, nicknames_home_only
) -> NSWFuelCoordinator:
    """Coordinator with a single NSW nickname."""
    return NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )


async def test_async_update_data_success(coordinator: NSWFuelCoordinator) -> None:
    """Coordinator returns favorites and cheapest data."""
    data = await coordinator._async_update_data()

    assert "favorites" in data
    assert "cheapest" in data

    assert isinstance(data["favorites"], dict)
    assert isinstance(data["cheapest"], dict)
    assert "Home" in data["cheapest"]


async def test_update_favorite_stations(coordinator: NSWFuelCoordinator) -> None:
    """Favorites map station key to fuel prices."""
    favorites = await coordinator._update_favorite_stations()

    assert (STATION_NSW_A, "NSW") in favorites
    fuels = favorites[(STATION_NSW_A, "NSW")]

    assert DEFAULT_FUEL_TYPE in fuels
    assert fuels[DEFAULT_FUEL_TYPE].price is not None


async def test_update_cheapest_stations_e10_u91(
    hass: HomeAssistant, mock_api_client, nicknames_home_only
) -> None:
    """E10 prices are merged, sorted with U91, and cheapest two returned."""

    # Force predictable data with interleaving prices
    # U91: 170, 165
    # E10: 168, 160  -> should win overall cheapest
    async def fake_within_radius(latitude, longitude, radius=25, fuel_type=None):
        station = Station(
            ident=None,
            brand="Test",
            code=999,
            name="Test Station",
            address="Test",
            latitude=latitude,
            longitude=longitude,
            au_state="NSW",
        )

        if fuel_type == DEFAULT_FUEL_TYPE:  # U91
            return [
                StationPrice(
                    station=station,
                    price=Price(
                        fuel_type="U91",
                        price=170.0,
                        last_updated="2024-01-01T00:00:00Z",
                        price_unit="c/L",
                        station_code=999,
                    ),
                ),
                StationPrice(
                    station=station,
                    price=Price(
                        fuel_type="U91",
                        price=165.0,
                        last_updated="2024-01-01T00:00:00Z",
                        price_unit="c/L",
                        station_code=999,
                    ),
                ),
            ]

        # E10
        return [
            StationPrice(
                station=station,
                price=Price(
                    fuel_type="E10",
                    price=168.0,
                    last_updated="2024-01-01T00:00:00Z",
                    price_unit="c/L",
                    station_code=999,
                ),
            ),
            StationPrice(
                station=station,
                price=Price(
                    fuel_type="E10",
                    price=160.0,
                    last_updated="2024-01-01T00:00:00Z",
                    price_unit="c/L",
                    station_code=999,
                ),
            ),
        ]

    mock_api_client.get_fuel_prices_within_radius.side_effect = fake_within_radius

    coordinator = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )

    result = await coordinator._update_cheapest_stations()
    home = result["Home"]

    # 🔒 Final list is truncated to 2
    assert len(home) == 2

    # 🔒 Sorted globally by price (not per-fuel)
    assert home[0]["price"] == 160.0
    assert home[1]["price"] == 165.0

    # 🔒 Cross-fuel merge occurred
    assert {item["fuel_type"] for item in home} == {"E10", "U91"}

    # 🔒 Correct structure preserved
    assert home[0]["station_name"] == "Test Station"
    assert home[0]["au_state"] == "NSW"


async def test_update_cheapest_stations_u91(
    hass: HomeAssistant, mock_api_client, nicknames_home_and_hobart
) -> None:
    """TAS nickname should only return default fuel type."""
    coordinator = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_and_hobart,
        scan_interval=timedelta(minutes=5),
    )

    cheapest = await coordinator._update_cheapest_stations()

    assert "Hobart" in cheapest

    fuels = {item["fuel_type"] for item in cheapest["Hobart"]}
    assert fuels == {DEFAULT_FUEL_TYPE}


async def test_async_update_auth_failure(
    hass: HomeAssistant, mock_api_client, nicknames_home_only
) -> None:
    """Auth error raises ConfigEntryAuthFailed."""
    mock_api_client.get_fuel_prices_for_station = AsyncMock(
        side_effect=NSWFuelApiClientAuthError("bad auth")
    )

    coordinator = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


async def test_async_update_api_failure(
    hass: HomeAssistant, mock_api_client, nicknames_home_only
) -> None:
    """API error raises UpdateFailed."""
    mock_api_client.get_fuel_prices_for_station = AsyncMock(
        side_effect=NSWFuelApiClientError("boom")
    )

    coordinator = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


def test_extract_locations_missing_block(hass: HomeAssistant, mock_api_client) -> None:
    """Nickname without location block raises TypeError."""
    nicknames = {"Home": {"stations": []}}

    with pytest.raises(TypeError):
        NSWFuelCoordinator(
            hass=hass,
            api=mock_api_client,
            nicknames=nicknames,
            scan_interval=timedelta(minutes=5),
        )


def test_extract_locations_missing_lat_lon(
    hass: HomeAssistant, mock_api_client
) -> None:
    """Nickname without lat/lon raises ValueError."""
    nicknames = {"Home": {"location": {}, "stations": []}}

    with pytest.raises(ValueError):
        NSWFuelCoordinator(
            hass=hass,
            api=mock_api_client,
            nicknames=nicknames,
            scan_interval=timedelta(minutes=5),
        )


def test_extract_locations_non_numeric(hass: HomeAssistant, mock_api_client) -> None:
    """Non-numeric coordinates raise TypeError."""
    nicknames = {
        "Home": {
            "location": {"latitude": "bad", "longitude": "data"},
            "stations": [],
        }
    }

    with pytest.raises(TypeError):
        NSWFuelCoordinator(
            hass=hass,
            api=mock_api_client,
            nicknames=nicknames,
            scan_interval=timedelta(minutes=5),
        )


def test_extract_locations_empty(hass: HomeAssistant, mock_api_client) -> None:
    """At least one nickname is required."""
    with pytest.raises(ValueError):
        NSWFuelCoordinator(
            hass=hass,
            api=mock_api_client,
            nicknames={},
            scan_interval=timedelta(minutes=5),
        )


def test_nicknames_property(coordinator: NSWFuelCoordinator) -> None:
    """Nicknames property exposes configured nicknames."""
    names = coordinator.nicknames

    assert names == ["Home"]
