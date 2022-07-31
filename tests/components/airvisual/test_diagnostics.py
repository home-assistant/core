"""Test AirVisual diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_airvisual):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "title": "Mock Title",
            "data": {
                "api_key": REDACTED,
                "integration_type": "Geographical Location by Latitude/Longitude",
                "latitude": REDACTED,
                "longitude": REDACTED,
            },
            "options": {
                "show_on_map": True,
            },
        },
        "data": {
            "city": REDACTED,
            "country": REDACTED,
            "current": {
                "weather": {
                    "ts": "2021-09-03T21:00:00.000Z",
                    "tp": 23,
                    "pr": 999,
                    "hu": 45,
                    "ws": 0.45,
                    "wd": 252,
                    "ic": "10d",
                },
                "pollution": {
                    "ts": "2021-09-04T00:00:00.000Z",
                    "aqius": 52,
                    "mainus": "p2",
                    "aqicn": 18,
                    "maincn": "p2",
                },
            },
            "location": {
                "coordinates": REDACTED,
                "type": "Point",
            },
            "state": REDACTED,
        },
    }
