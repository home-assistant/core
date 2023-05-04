"""Test AirVisual diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_config_entry,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 3,
            "domain": "airvisual",
            "title": REDACTED,
            "data": {
                "integration_type": "Geographical Location by Latitude/Longitude",
                "api_key": REDACTED,
                "latitude": REDACTED,
                "longitude": REDACTED,
            },
            "options": {"show_on_map": True},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "data": {
            "city": REDACTED,
            "state": REDACTED,
            "country": REDACTED,
            "location": {"type": "Point", "coordinates": REDACTED},
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
        },
    }
