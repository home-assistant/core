"""Tests for Fritz!Tools diagnostics platform."""

from __future__ import annotations

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.fritz.const import DOMAIN
from homeassistant.core import HomeAssistant

from .const import MOCK_USER_DATA

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    fc_class_mock,
    fh_class_mock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_DATA)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(hass, hass_client, entry)
    assert result == snapshot(
        exclude=props("created_at", "modified_at", "entry_id", "last_activity")
    )
