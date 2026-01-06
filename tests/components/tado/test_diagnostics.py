"""Test the Tado component diagnostics."""

import pytest
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.tado.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("init_integration")
async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test if get_config_entry_diagnostics returns the correct data."""
    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at"))
