"""Tests for the diagnostics data provided by the BSBLan integration."""
import json

from aiohttp import ClientSession

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSession,
    init_integration: MockConfigEntry,
):
    """Test diagnostics."""

    diagnostics_fixture = json.loads(load_fixture("bsblan/diagnostics.json"))

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
        == diagnostics_fixture
    )
