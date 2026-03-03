"""Tests for NSW Fuel UI sensor platform."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.nsw_fuel_station.const import DOMAIN
from homeassistant.components.nsw_fuel_station.coordinator import NSWFuelCoordinator
from homeassistant.components.nsw_fuel_station.sensor import (
    CheapestFuelPriceSensor,
    FuelPriceSensor,
    _attribution_for_state,
    async_setup_entry,
    create_cheapest_fuel_sensors,
    create_favorite_station_sensors,
)

from tests.common import MockConfigEntry

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
def nicknames_home_only() -> dict:
    """Single NSW nickname with location and favorites."""
    return {
        "Home": {
            "location": {"latitude": -35.28, "longitude": 149.13},
            "stations": [
                {
                    "station_code": 111,
                    "au_state": "NSW",
                    "station_name": "Ampol Batemans Bay",
                    "fuel_types": ["U91", "E10"],
                }
            ],
        }
    }


@pytest.fixture
async def coordinator(
    hass: HomeAssistant, mock_api_client, nicknames_home_only
) -> NSWFuelCoordinator:
    """Initialise coordinator with data loaded."""
    coord = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )
    await coord.async_refresh()
    return coord


# -----------------------
# async_setup_entry
# -----------------------


@pytest.mark.asyncio
async def test_async_setup_entry_creates_entities(
    hass: HomeAssistant, coordinator
) -> None:
    """Prepare a mock config entry with data including nicknames."""
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "nicknames": {
                "Home": {
                    "stations": [
                        {
                            "station_code": 111,
                            "au_state": "NSW",
                            "fuel_types": ["U91", "E10"],
                            "station_name": "My Fuel Station",
                        }
                    ]
                }
            }
        },
        entry_id="test_entry_id",
    )
    mock_config_entry.add_to_hass(hass)

    # Assign config entry to coordinator
    coordinator.config_entry = mock_config_entry
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][mock_config_entry.entry_id] = coordinator

    entities = []

    def _add_entities(new_entities) -> None:
        entities.extend(new_entities)

    with patch.object(coordinator, "async_config_entry_first_refresh", new=AsyncMock()):
        await async_setup_entry(hass, mock_config_entry, _add_entities)

    assert entities
    assert any(isinstance(e, FuelPriceSensor) for e in entities)
    assert any(isinstance(e, CheapestFuelPriceSensor) for e in entities)


# -----------------------
# Favorite sensors
# -----------------------


def test_create_favorite_station_sensors(coordinator) -> None:
    """Favorite sensors are created per fuel type and per station."""
    nicknames = {
        "Home": {
            "stations": [
                {
                    "station_code": 111,
                    "au_state": "NSW",
                    "station_name": "Station One",
                    "fuel_types": ["U91", "E10"],
                },
                {
                    "station_code": 222,
                    "au_state": "NSW",
                    "station_name": "Station Two",
                    "fuel_types": ["U91"],
                },
            ]
        }
    }

    sensors = create_favorite_station_sensors(coordinator, nicknames)

    # We expect 3 sensors total (2 fuel types for first station, 1 for second)
    assert len(sensors) == 3

    # Check fuel types present
    assert {s._fuel_type for s in sensors} == {"U91", "E10"}

    # Check station codes present (both stations)
    assert {s._station_code for s in sensors} == {111, 222}

    # Check station names present
    assert {s._station_name for s in sensors} == {"Station One", "Station Two"}

    # Check one sensor for example details
    sensor = sensors[0]
    assert isinstance(sensor, FuelPriceSensor)
    assert sensor.device_info["name"] == "Home"
    assert sensor.icon == "mdi:gas-station"


async def test_favorite_sensor_native_value(coordinator, nicknames_home_only) -> None:
    """Favorite sensor reads value from coordinator favorites data."""
    sensors = create_favorite_station_sensors(coordinator, nicknames_home_only)

    u91_sensor = next(s for s in sensors if s._fuel_type == "U91")
    value = u91_sensor.native_value

    assert value is not None
    assert value > 0


async def test_favorite_sensor_no_data_returns_none(
    hass: HomeAssistant,
    mock_api_client,
    nicknames_home_only,
) -> None:
    """Favorite sensor returns None if coordinator has no data."""
    coord = NSWFuelCoordinator(
        hass=hass,
        api=mock_api_client,
        nicknames=nicknames_home_only,
        scan_interval=timedelta(minutes=5),
    )

    sensors = create_favorite_station_sensors(coord, nicknames_home_only)
    assert sensors[0].native_value is None


# -----------------------
# Cheapest sensors
# -----------------------


def test_create_cheapest_fuel_sensors_always_two(coordinator) -> None:
    """Two cheapest sensors are created per nickname."""
    sensors = create_cheapest_fuel_sensors(coordinator)

    assert len(sensors) == 2
    assert all(isinstance(s, CheapestFuelPriceSensor) for s in sensors)

    ranks = {s._rank for s in sensors}
    assert ranks == {1, 2}


async def test_cheapest_sensor_native_value_and_attributes(coordinator) -> None:
    """Cheapest sensor exposes price and dynamic attributes."""
    sensors = create_cheapest_fuel_sensors(coordinator)

    first = next(s for s in sensors if s._rank == 1)

    assert first.native_value is not None

    attrs = first.extra_state_attributes
    assert attrs is not None
    assert "station_code" in attrs
    assert "station_name" in attrs
    assert "fuel_type" in attrs
    assert "price" in attrs
    assert attrs["rank"] == 1


def test_cheapest_sensor_icon() -> None:
    """Rank 1 uses highlighted icon."""
    sensor1 = CheapestFuelPriceSensor(None, "Home", 1)
    sensor2 = CheapestFuelPriceSensor(None, "Home", 2)

    assert sensor1.icon == "mdi:gas-station-in-use"
    assert sensor2.icon == "mdi:gas-station"


# -----------------------
# Attribution
# -----------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        ("TAS", "FuelCheck TAS"),
        ("NSW", "NSW Government FuelCheck"),
        (None, "NSW Government FuelCheck"),
    ],
)
def test_attribution_for_state(state, expected) -> None:
    """Correct attribution string is returned."""
    assert _attribution_for_state(state) == expected
