"""Tests for the CityBikes sensor platform."""

from importlib import import_module
import sys
from types import SimpleNamespace
from unittest.mock import patch


def _import_citybikes_sensor_module():
    """Import the citybikes sensor module with a stubbed client library."""
    citybikes_module = SimpleNamespace(__version__="0.0.0")
    citybikes_asyncio_module = SimpleNamespace(Client=object)

    sys.modules.pop("homeassistant.components.citybikes.sensor", None)
    with patch.dict(
        sys.modules,
        {
            "citybikes": citybikes_module,
            "citybikes.asyncio": citybikes_asyncio_module,
        },
    ):
        return import_module("homeassistant.components.citybikes.sensor")


async def test_citybikes_station_exposes_ebikes_from_station_extra() -> None:
    """Test CityBikesStation exposes free ebikes from station.extra."""
    citybikes_sensor = _import_citybikes_sensor_module()
    station = SimpleNamespace(
        id="station-1",
        name="Station 1",
        free_bikes=5,
        empty_slots=8,
        latitude=40.0,
        longitude=-73.0,
        timestamp="2026-03-22T00:00:00Z",
        extra={citybikes_sensor.ATTR_UID: "uid-1", "ebikes": 2},
    )
    network = SimpleNamespace(stations=[station])
    entity = citybikes_sensor.CityBikesStation(network, "station-1", "sensor.station_1")

    await entity.async_update()

    assert entity.native_value == 5
    assert entity.extra_state_attributes == {
        citybikes_sensor.ATTR_UID: "uid-1",
        citybikes_sensor.ATTR_LATITUDE: 40.0,
        citybikes_sensor.ATTR_LONGITUDE: -73.0,
        citybikes_sensor.ATTR_EMPTY_SLOTS: 8,
        citybikes_sensor.ATTR_FREE_EBIKES: 2,
        citybikes_sensor.ATTR_TIMESTAMP: "2026-03-22T00:00:00Z",
    }


async def test_citybikes_station_handles_missing_ebikes() -> None:
    """Test CityBikesStation handles stations without ebike data."""
    citybikes_sensor = _import_citybikes_sensor_module()
    station = SimpleNamespace(
        id="station-1",
        name="Station 1",
        free_bikes=5,
        empty_slots=8,
        latitude=40.0,
        longitude=-73.0,
        timestamp="2026-03-22T00:00:00Z",
        extra={citybikes_sensor.ATTR_UID: "uid-1"},
    )
    network = SimpleNamespace(stations=[station])
    entity = citybikes_sensor.CityBikesStation(network, "station-1", "sensor.station_1")

    await entity.async_update()

    assert entity.extra_state_attributes[citybikes_sensor.ATTR_FREE_EBIKES] is None
