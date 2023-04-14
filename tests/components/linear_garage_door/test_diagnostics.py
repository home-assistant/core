"""Test diagnostics of Linear Garage Door."""

from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant, hass_client: ClientSessionGenerator
) -> None:
    """Test config entry diagnostics."""
    entry = await async_init_integration(hass)
    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result["entry"]["data"] == {
        "email": "**REDACTED**",
        "password": "**REDACTED**",
        "site_id": "test-site-id",
        "device_id": "test-uuid",
    }
    assert result["coordinator_data"] == {
        "test1": {
            "name": "Test Garage 1",
            "subdevices": {
                "GDO": {"Open_B": "true", "Open_P": "100"},
                "Light": {"On_B": "true", "On_P": "100"},
            },
        },
        "test2": {
            "name": "Test Garage 2",
            "subdevices": {
                "GDO": {"Open_B": "false", "Open_P": "0"},
                "Light": {"On_B": "false", "On_P": "0"},
            },
        },
    }
