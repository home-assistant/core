"""Test the Tado component diagnostics."""

from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.tado.const import DOMAIN
from homeassistant.core import HomeAssistant

from .util import async_init_integration

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_get_config_entry_diagnostics(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test if get_config_entry_diagnostics returns the correct data."""
    await async_init_integration(hass)

    config_entry: MockConfigEntry = hass.config_entries.async_entries(DOMAIN)[0]
    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )
    assert diagnostics == snapshot(exclude=props("created_at", "modified_at"))
