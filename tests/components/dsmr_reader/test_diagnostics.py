"""Test the DSMR Reader component diagnostics."""

from unittest.mock import patch

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test if get_config_entry_diagnostics returns the correct data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=DOMAIN,
        options={},
        entry_id="TEST_ENTRY_ID",
        unique_id="UNIQUE_TEST_ID",
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dsmr_reader.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at"))
