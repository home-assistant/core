"""Tests for Starlink diagnostics."""
import json

import aiohttp

from homeassistant.components.starlink.const import DOMAIN
from homeassistant.const import CONF_IP_ADDRESS
from homeassistant.core import HomeAssistant

from .patchers import COORDINATOR_SUCCESS_PATCHER

from tests.common import MockConfigEntry, load_fixture
from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_diagnostics(hass: HomeAssistant, hass_client: aiohttp.client) -> None:
    """Test generating diagnostics for a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_IP_ADDRESS: "1.2.3.4:0000"},
    )

    with COORDINATOR_SUCCESS_PATCHER:
        entry.add_to_hass(hass)

        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

        assert diag == json.loads(load_fixture("diagnostics_expected.json", "starlink"))
