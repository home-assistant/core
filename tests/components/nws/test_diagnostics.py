"""Test NWS diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.components import nws
from homeassistant.core import HomeAssistant

from .const import NWS_CONFIG

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
    mock_simple_nws,
) -> None:
    """Test config entry diagnostics."""

    entry = MockConfigEntry(
        domain=nws.DOMAIN,
        data=NWS_CONFIG,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert result == snapshot
