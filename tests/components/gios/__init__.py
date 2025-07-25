"""Tests for GIOS."""

from unittest.mock import patch

from homeassistant.components.gios.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import (
    MockConfigEntry,
    async_load_json_array_fixture,
    async_load_json_object_fixture,
)

STATIONS = [
    {
        "Identyfikator stacji": 123,
        "Nazwa stacji": "Test Name 1",
        "WGS84 φ N": "99.99",
        "WGS84 λ E": "88.88",
    },
    {
        "Identyfikator stacji": 321,
        "Nazwa stacji": "Test Name 2",
        "WGS84 φ N": "77.77",
        "WGS84 λ E": "66.66",
    },
]


async def init_integration(
    hass: HomeAssistant, incomplete_data=False, invalid_indexes=False
) -> MockConfigEntry:
    """Set up the GIOS integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Home",
        unique_id="123",
        data={"station_id": 123, "name": "Home"},
        entry_id="86129426118ae32020417a53712d6eef",
    )

    indexes = await async_load_json_object_fixture(hass, "indexes.json", DOMAIN)
    station = await async_load_json_array_fixture(hass, "station.json", DOMAIN)
    sensors = await async_load_json_object_fixture(hass, "sensors.json", DOMAIN)
    if incomplete_data:
        indexes["AqIndex"] = "foo"
        sensors["pm10"]["Lista danych pomiarowych"][0]["Wartość"] = None
        sensors["pm10"]["Lista danych pomiarowych"][1]["Wartość"] = None
    if invalid_indexes:
        indexes = {}

    with (
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_stations",
            return_value=STATIONS,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_station",
            return_value=station,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_all_sensors",
            return_value=sensors,
        ),
        patch(
            "homeassistant.components.gios.coordinator.Gios._get_indexes",
            return_value=indexes,
        ),
    ):
        entry.add_to_hass(hass)
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
