"""Tests for the CityBikes sensor platform."""

from types import SimpleNamespace

from homeassistant.components.citybikes.sensor import (
    ATTR_EMPTY_SLOTS,
    ATTR_FREE_EBIKES,
    ATTR_LATITUDE,
    ATTR_LONGITUDE,
    ATTR_TIMESTAMP,
    ATTR_UID,
    CityBikesStation,
)


def _create_station(extra: dict[str, object]) -> SimpleNamespace:
    """Create a CityBikes station test double."""
    return SimpleNamespace(
        id="station-1",
        name="Station 1",
        free_bikes=5,
        empty_slots=8,
        latitude=40.0,
        longitude=-73.0,
        timestamp="2026-03-22T00:00:00Z",
        extra=extra,
    )


async def test_citybikes_station_exposes_ebikes_from_station_extra() -> None:
    """Test CityBikesStation exposes free ebikes from station.extra."""
    station = _create_station({ATTR_UID: "uid-1", "ebikes": 2})
    network = SimpleNamespace(stations=[station])
    entity = CityBikesStation(network, "station-1", "sensor.station_1")

    await entity.async_update()

    assert entity.native_value == 5
    assert entity.extra_state_attributes == {
        ATTR_UID: "uid-1",
        ATTR_LATITUDE: 40.0,
        ATTR_LONGITUDE: -73.0,
        ATTR_EMPTY_SLOTS: 8,
        ATTR_FREE_EBIKES: 2,
        ATTR_TIMESTAMP: "2026-03-22T00:00:00Z",
    }


async def test_citybikes_station_handles_missing_ebikes() -> None:
    """Test CityBikesStation handles stations without ebike data."""
    station = _create_station({ATTR_UID: "uid-1"})
    network = SimpleNamespace(stations=[station])
    entity = CityBikesStation(network, "station-1", "sensor.station_1")

    await entity.async_update()

    assert entity.extra_state_attributes[ATTR_FREE_EBIKES] is None
