"""Test the TFA.me integration: conftest.py."""

# For test run: "pytest ./tests/components/tfa_me/ --cov=homeassistant.components.tfa_me --cov-report term-missing -vv"

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from homeassistant.components.tfa_me.const import CONF_NAME_WITH_STATION_ID, DOMAIN
from homeassistant.components.tfa_me.coordinator import (
    DataUpdateCoordinator,
    TFAmeConfigEntry,
    TFAmeDataCoordinator,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import AsyncMock, Mock, MockConfigEntry


@pytest.fixture
def mock_config_entry(hass: HomeAssistant, tfa_me_mock_entry) -> ConfigEntry:
    """Create dummy ConfigEntry."""
    entry = MagicMock(spec=TFAmeConfigEntry)
    entry.entry_id = "test-1234"
    entry.domain = DOMAIN
    coordy = TFAmeDataCoordinator(
        hass=hass,
        config_entry=tfa_me_mock_entry,
        host="192.168.1.46",
        interval=timedelta(30),
        name_with_station_id=False,
    )
    coordy.sensor_entity_list = []
    entry.runtime_data = coordy
    return entry


@pytest.fixture
def tfa_me_mock_entry(hass: HomeAssistant, tfa_me_mock_coordinator):
    """Return a mock ConfigEntry."""
    entry = AsyncMock()
    entry.entry_id = "1234"
    entry.runtime_data = tfa_me_mock_coordinator
    return entry


@pytest.fixture
def tfa_me_options_flow_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create default mock config entry for options flow test."""
    default_entry_x = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
            CONF_NAME_WITH_STATION_ID: True,
        },
        unique_id="test-1234",
    )
    default_entry_x.add_to_hass(hass)
    return default_entry_x


@pytest.fixture
def tfa_me_mock_coordinator():
    """Return a mock coordinator with dummy data."""
    coordinator = MagicMock(spec=DataUpdateCoordinator)
    coordinator.async_add_listener = Mock(return_value=lambda: None)
    coordinator.async_request_refresh = AsyncMock()
    coordinator.async_update = AsyncMock()
    coordinator.host = "192.168.1.10"
    coordinator.name_with_station_id = False
    coordinator.sensor_entity_list = []
    now = datetime.now().timestamp()
    coordinator.gateway_id = "017654321"
    coordinator.gateway_sw = "1.12345 / 1"
    # Some entities used for 100% test coverage
    coordinator.data = {
        "sensor.017654321_a01234567_temperature": {
            "value": "23.5",
            "unit": "°C",
            "ts": int(now),
        },
        "sensor.017654321_a2ffffffb_wind_direction": {
            "value": "8",
            "unit": "°",
            "ts": int(now),
        },
        "sensor.017654321_a2ffffffb_wind_direction_deg": {
            "value": "8",
            "unit": "°",
            "ts": int(now),
        },
        "sensor.017654321_a2ffffffc_wind_direction_deg": {
            "value": "xxx",  # Set to invalid value
            "unit": "°",
            "ts": int(now),
        },
        "sensor.017654321_a2ffffffc_rssi": {
            "value": "222",
            "unit": "/255",
            "ts": int(now) - 1000000,  # Set to old value
        },
        "sensor.017654321_a1fffffea_rain": {
            "value": "7.4",
            "unit": "mm",
            "ts": int(now),
            "reset_rain": False,
        },
        "sensor.017654321_a1fffffea_rain_rel": {
            "value": "7.4",
            "unit": "mm",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.017654321_a1fffffea_rain_1_hour": {
            "value": "7.4",
            "unit": "mm",
            "ts": int(now) - 60,
            "reset_rain": True,
        },
        "sensor.017654321_a1fffffec_rain_24_hours": {
            "value": "7.4",
            "unit": "mm",
            "ts": int(now) - 60,
            "reset_rain": False,
        },
        "sensor.017654321_a1fffffea_rain_24_hours": {
            "value": "7.4",
            "unit": "mm",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.017654321_017654321_barometric_pressure": {
            "value": "1000.1",
            "unit": "hPa",
            "ts": int(now),
            "info": "",
        },
        "sensor.017654321_017654322_barometric_pressure": {
            "value": "1000.1",
            "unit": "hPa",
            "ts": int(now),
        },
    }

    return coordinator


# Original JSON data from a TFA.me station for snapahot testing
FAKE_JSON = {
    "gateway_id": "05B3E4E44",
    "sensors": [
        {
            "sensor_id": "a204e4df6",
            "name": "A204E4DF6",
            "timestamp": "2025-11-26T15:11:26Z",
            "ts": "1764169886",
            "measurements": {
                "rssi": {"value": "218", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": "No"},
                "wind_direction": {"value": "8", "unit": ""},
                "wind_speed": {"value": "0.0", "unit": "m/s"},
                "wind_gust": {"value": "0.0", "unit": "m/s"},
            },
        },
        {
            "sensor_id": "a4481290f",
            "name": "A4481290F",
            "timestamp": "2025-11-26T15:10:42Z",
            "ts": "1764169842",
            "measurements": {
                "rssi": {"value": "174", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": "No"},
                "temperature": {"value": "15.1", "unit": "°C"},
                "humidity": {"value": "56", "unit": "%"},
                "temperature_probe": {"value": "15.1", "unit": "°C"},
            },
        },
        {
            "sensor_id": "a6f169ad1",
            "name": "A6F169AD1",
            "timestamp": "2025-11-26T15:11:05Z",
            "ts": "1764169865",
            "measurements": {
                "rssi": {"value": "227", "unit": "/255"},
                "lowbatt": {"value": "1", "unit": "Yes"},
                "temperature": {"value": "23.9", "unit": "°C"},
                "humidity": {"value": "38", "unit": "%"},
            },
        },
        {
            "sensor_id": "a2ffffffb",
            "name": "A2FFFFFFB",
            "timestamp": "2025-11-26T15:10:23Z",
            "ts": "1764169823",
            "measurements": {
                "rssi": {"value": "218", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": "No"},
                "wind_direction": {"value": "8", "unit": ""},
                "wind_speed": {"value": "0.0", "unit": "m/s"},
                "wind_gust": {"value": "0.0", "unit": "m/s"},
            },
        },
        {
            "sensor_id": "a364f3d67",
            "name": "A364F3D67",
            "timestamp": "2025-11-26T15:08:47Z",
            "ts": "1764169727",
            "measurements": {
                "rssi": {"value": "226", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": "No"},
                "temperature": {"value": "23.9", "unit": "°C"},
            },
        },
        {
            "sensor_id": "05b3e4e44",
            "name": "05B3E4E44",
            "timestamp": "2025-11-26T15:07:26Z",
            "ts": "1764169646",
            "measurements": {
                "rssi": {"value": "255", "unit": "/255"},
                "lowbatt": {"value": "1", "unit": "Yes"},
                "temperature": {"value": "23.8", "unit": "°C"},
                "humidity": {"value": "35", "unit": "%"},
                "barometric_pressure": {"value": "1011.0", "unit": "hPa"},
            },
        },
        {
            "sensor_id": "a1fffffea",
            "name": "A1FFFFFEA",
            "timestamp": "2025-11-26T15:01:57Z",
            "ts": "1764169317",
            "measurements": {
                "rssi": {"value": "192", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": "No"},
                "rain": {"value": "7.4", "unit": "mm"},
            },
        },
    ],
}
