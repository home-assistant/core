"""Test WiZ diagnostics."""
from . import async_setup_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass, hass_client):
    """Test generating diagnostics for a config entry."""
    _, entry = await async_setup_integration(hass)
    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == {
        "data": {
            "homeId": "**REDACTED**",
            "mocked": "mocked",
            "roomId": "**REDACTED**",
        },
        "entry": {"data": {"host": "1.1.1.1"}, "title": "Mock Title"},
    }
