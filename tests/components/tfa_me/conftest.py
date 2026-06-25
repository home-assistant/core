"""Test the TFA.me integration: conftest.py."""

import pytest

from homeassistant.components.tfa_me.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def tfa_me_options_flow_mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create default mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "127.0.0.1",
        },
        unique_id="test-1234",
    )


@pytest.fixture
def tfa_me_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a default TFA.me config entry."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_IP_ADDRESS: "192.168.1.10",
        },
        title="TFA.me Station '05B3E4E44'",
    )
    entry.add_to_hass(hass)
    return entry


# Original JSON data from a TFA.me station for snapshot testing
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
                "lowbatt": {"value": "0", "unit": ""},
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
                "lowbatt": {"value": "0", "unit": ""},
                "rain": {"value": "7.4", "unit": "mm"},
            },
        },
        {
            "sensor_id": "bb1234567",  # invalid sensor type, sensor types 'bb' does not exist
            "name": "BB1234567",
            "timestamp": "2025-11-26T15:01:57Z",
            "ts": "1764169317",
            "measurements": {
                "rssi": {"value": "192", "unit": "/255"},
                "lowbatt": {"value": "0", "unit": ""},
                "rain": {"value": "7.4", "unit": "mm"},
            },
        },
    ],
}
