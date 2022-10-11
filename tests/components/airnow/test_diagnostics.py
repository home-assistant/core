"""Test AirNow diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_airnow):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "data": {
                "api_key": REDACTED,
                "latitude": REDACTED,
                "longitude": REDACTED,
                "radius": 75,
            },
        },
        "data": {
            "O3": 0.048,
            "PM2.5": 8.9,
            "HourObserved": 15,
            "DateObserved": "2020-12-20",
            "StateCode": REDACTED,
            "ReportingArea": REDACTED,
            "Latitude": REDACTED,
            "Longitude": REDACTED,
            "PM10": 12,
            "AQI": 44,
            "Category.Number": 1,
            "Category.Name": "Good",
            "Pollutant": "O3",
        },
    }
