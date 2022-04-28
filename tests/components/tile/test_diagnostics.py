"""Test Tile diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, config_entry, hass_client, setup_tile):
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(hass, hass_client, config_entry) == {
        "tiles": [
            {
                "accuracy": 13.496111,
                "altitude": REDACTED,
                "archetype": "WALLET",
                "dead": False,
                "firmware_version": "01.12.14.0",
                "hardware_version": "02.09",
                "kind": "TILE",
                "last_timestamp": "2020-08-12T17:55:26",
                "latitude": REDACTED,
                "longitude": REDACTED,
                "lost": False,
                "lost_timestamp": "1969-12-31T23:59:59.999000",
                "name": "Wallet",
                "ring_state": "STOPPED",
                "uuid": REDACTED,
                "visible": True,
                "voip_state": "OFFLINE",
            }
        ]
    }
