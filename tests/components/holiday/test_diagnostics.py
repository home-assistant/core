"""Test Holiday diagnostics."""

from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.holiday.const import DOMAIN
from homeassistant.core import HomeAssistant


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="1",
        title="Germany, BW",
        data={"country": "DE", "province": "BW"},
        options={"categories": ["catholic"]},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    diag = await get_diagnostics_for_config_entry(hass, hass_client, entry)

    assert diag == snapshot(exclude=props("created_at", "modified_at"))
