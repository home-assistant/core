"""Tests for the buienradar component."""

import datetime as dt
from typing import Any

from buienradar.constants import (
    ATTRIBUTION,
    CONDCODE,
    CONDITION,
    DATETIME,
    DETAILED,
    EXACT,
    EXACTNL,
    FEELTEMPERATURE,
    FORECAST,
    HUMIDITY,
    IMAGE,
    MAX_TEMP,
    MEASURED,
    MIN_TEMP,
    PRECIPITATION_FORECAST,
    PRESSURE,
    RAIN,
    RAIN_CHANCE,
    STATIONNAME,
    TEMPERATURE,
    TIMEFRAME,
    VISIBILITY,
    WINDAZIMUTH,
    WINDGUST,
    WINDSPEED,
)
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.buienradar.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE
from homeassistant.core import HomeAssistant

TEST_LATITUDE = 51.5288504
TEST_LONGITUDE = 5.4002156
TEST_CFG_DATA = {CONF_LATITUDE: TEST_LATITUDE, CONF_LONGITUDE: TEST_LONGITUDE}

TEST_DATA: dict[str, Any] = {
    ATTRIBUTION: "Data provided by buienradar.nl",
    STATIONNAME: "Eindhoven (6370)",
    MEASURED: dt.datetime(2026, 11, 20, 12, 0, tzinfo=dt.UTC),
    CONDITION: {
        CONDCODE: "c",
        CONDITION: "cloudy",
        DETAILED: "cloudy",
        EXACT: "Heavily clouded",
        EXACTNL: "Zwaar bewolkt",
        IMAGE: "https://cdn.buienradar.nl/resources/images/icons/weather/30x30/c.png",
    },
    TEMPERATURE: 8.2,
    FEELTEMPERATURE: 6.1,
    HUMIDITY: 87,
    PRESSURE: 1012.4,
    VISIBILITY: 23400,
    WINDGUST: 7.2,
    WINDSPEED: 4.1,
    WINDAZIMUTH: 225,
    PRECIPITATION_FORECAST: {TIMEFRAME: 60, "average": 0.0, "total": 0.0},
    FORECAST: [
        {
            DATETIME: dt.datetime(2026, 11, 21, tzinfo=dt.UTC),
            CONDITION: {CONDCODE: "f"},
            MIN_TEMP: 4.0,
            MAX_TEMP: 9.0,
            RAIN: 2.5,
            RAIN_CHANCE: 60,
            WINDAZIMUTH: 200,
            WINDSPEED: 5,
        },
        {
            DATETIME: dt.datetime(2026, 11, 22, tzinfo=dt.UTC),
            CONDITION: {CONDCODE: "a"},
            MIN_TEMP: 2.0,
            MAX_TEMP: 7.0,
            RAIN: 0.0,
            RAIN_CHANCE: 10,
            WINDAZIMUTH: 90,
            WINDSPEED: 3,
        },
    ],
}


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id="TEST_ID", data=TEST_CFG_DATA)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
