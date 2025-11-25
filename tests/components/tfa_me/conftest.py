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
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = tfa_me_mock_coordinator
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
    coordinator.data = {
        "sensor.a01234567_temperature": {
            "sensor_id": "a01234567",
            "gateway_id": "017654321",
            "sensor_name": "A01234567",
            "measurement": "temperature",
            "value": "23.5",
            "unit": "°C",
            "timestamp": "2025-09-01T08:46:01Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_rssi": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "rssi",
            "value": "233",
            "unit": "/255",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_lowbatt": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt",
            "value": "1",
            "unit": "",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_lowbatt_txt": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "lowbatt_text",
            "value": "1",
            "text": "Yes",
            "uint": "",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
        },
        "sensor.a6f169ad1_temperature": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "temperature",
            "value": "24.7",
            "unit": "°C",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a6f169ad1_humidity": {
            "sensor_id": "a6f169ad1",
            "gateway_id": "017654321",
            "sensor_name": "A6F169AD1",
            "measurement": "humidity",
            "value": "50",
            "unit": "%",
            "timestamp": "2025-09-02T09:15:13Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_rssi": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "rssi",
            "value": "232",
            "unit": "/255",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_lowbatt": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "lowbatt",
            "value": "0",
            "unit": "",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a364f3d67_lowbatt_txt": {
            "sensor_id": "a364f3d67",
            "gateway_id": "99fffff9d",
            "sensor_name": "A364F3D67",
            "measurement": "lowbatt_text",
            "value": "0",
            "text": "No",
            "uint": "",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
        },
        "sensor.a364f3d67_temperature": {
            "sensor_id": "a364f3d67",
            "gateway_id": "017654321",
            "sensor_name": "A364F3D67",
            "measurement": "temperature",
            "value": "24.5",
            "unit": "°C",
            "timestamp": "2025-09-02T09:12:33Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.a2ffffffb_wind_direction": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_direction",
            "value": "8",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffb_wind_direction_deg": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "wind_direction_deg",
            "value": "8",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffc_wind_direction_deg": {
            "sensor_id": "a2ffffffc",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFC",
            "measurement": "wind_direction_deg",
            "value": "xxx",
            "unit": "°",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now),
        },
        "sensor.a2ffffffc_rssi": {
            "sensor_id": "a2ffffffb",
            "gateway_id": "017654321",
            "sensor_name": "A2FFFFFFB",
            "measurement": "rssi",
            "value": "222",
            "unit": "/255",
            "timestamp": "2025-09-02T09:15:11Z",
            "ts": int(now) - 1000000,  # old
        },
        "sensor.a1fffffea_rain": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": False,
        },
        "sensor.a1fffffea_rain_rel": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.a1fffffea_rain_hour": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_1_hour",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now) - 60,
            "reset_rain": False,
        },
        "sensor.a1fffffec_rain_24hours": {
            "sensor_id": "a1fffffec",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEC",
            "measurement": "rain_24_hours",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now) - 60,
            "reset_rain": False,
        },
        "sensor.a1fffffeb_rain_hour": {
            "sensor_id": "a1fffffeb",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEB",
            "measurement": "rain_1_hour",
            "unit": "mm",
            "timestamp": "2025-09-02T07:36:30Z",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.a1fffffea_rain_24hours": {
            "sensor_id": "a1fffffea",
            "gateway_id": "017654321",
            "sensor_name": "A1FFFFFEA",
            "measurement": "rain_24_hours",
            "value": "7.4",
            "unit": "mm",
            "timestamp": "2025-09-02T09:36:28Z",
            "ts": int(now),
            "reset_rain": True,
        },
        "sensor.057654321_barometric_pressure": {
            "sensor_id": "057654321",
            "gateway_id": "057654321",
            "sensor_name": "057654321",
            "measurement": "barometric_pressure",
            "value": "1000.1",
            "unit": "hPa",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.057654322_barometric_pressure": {
            "sensor_id": "057654322",
            "gateway_id": "057654322",
            "sensor_name": "057654322",
            "value": "1000.1",
            "unit": "hPa",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
        "sensor.057654323_barometric_pressure": {
            "sensor_id": "057654323",
            "gateway_id": "057654323",
            "sensor_name": "057654323",
            "value": "1000.1",
            "timestamp": "2025-09-02T10:31:42Z",
            "ts": int(now),
            "info": "",
        },
    }

    return coordinator
