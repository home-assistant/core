"""Tests for the diagnostics data provided by the Whois integration."""
from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, init_integration
    ) == {
        "creation_date": "2019-01-01T00:00:00",
        "expiration_date": "2023-01-01T00:00:00",
        "last_updated": "2022-01-01T00:00:00+01:00",
        "status": "OK",
        "statuses": ["OK"],
        "dnssec": True,
    }
