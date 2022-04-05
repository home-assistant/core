"""The diagnostics tests for the Airzone platform."""

import json

from homeassistant.components.airzone.const import DOMAIN
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.common import load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_config_entry_diagnostics(hass: HomeAssistant, hass_client):
    """Test config entry diagnostics."""
    await async_init_integration(hass)
    assert hass.data[DOMAIN]

    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    diagnostics_fixture = json.loads(
        load_fixture("airzone/diagnostics_config_entry.json")
    )

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == diagnostics_fixture
    )
