"""Test WattTime diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_watttime):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "data": {
                "username": REDACTED,
                "password": REDACTED,
                "latitude": REDACTED,
                "longitude": REDACTED,
                "balancing_authority": "PJM New Jersey",
                "balancing_authority_abbreviation": "PJM_NJ",
            },
            "options": {},
        },
        "data": {
            "freq": "300",
            "ba": "CAISO_NORTH",
            "percent": "53",
            "moer": "850.743982",
            "point_time": "2019-01-29T14:55:00.00Z",
        },
    }
