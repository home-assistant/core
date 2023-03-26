"""Test WattTime diagnostics."""
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_watttime,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "entry": {
            "entry_id": config_entry.entry_id,
            "version": 1,
            "domain": "watttime",
            "title": REDACTED,
            "data": {
                "username": REDACTED,
                "password": REDACTED,
                "latitude": REDACTED,
                "longitude": REDACTED,
                "balancing_authority": REDACTED,
                "balancing_authority_abbreviation": REDACTED,
            },
            "options": {},
            "pref_disable_new_entities": False,
            "pref_disable_polling": False,
            "source": "user",
            "unique_id": REDACTED,
            "disabled_by": None,
        },
        "data": {
            "freq": "300",
            "ba": "CAISO_NORTH",
            "percent": "53",
            "moer": "850.743982",
            "point_time": "2019-01-29T14:55:00.00Z",
        },
    }
