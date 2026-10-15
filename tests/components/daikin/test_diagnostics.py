"""Tests for the diagnostics data provided by the Daikin integration."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.daikin.const import KEY_MAC
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from .test_config_flow import HOST, MAC

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    zone_device,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    entry = MockConfigEntry(
        domain="daikin",
        unique_id=MAC,
        data={CONF_HOST: HOST, KEY_MAC: MAC},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
