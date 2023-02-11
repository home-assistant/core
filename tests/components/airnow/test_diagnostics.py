"""Test AirNow diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant, config_entry, hass_client: ClientSessionGenerator, setup_airnow
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 1,
            "domain": "airnow",
            "title": REDACTED,
            "data": {
                "api_key": REDACTED,
                "latitude": REDACTED,
                "longitude": REDACTED,
                "radius": 75,
            },
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
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
