"""Test Discovergy diagnostics."""

from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.components.discovergy.conftest import ComponentSetup
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry: MockConfigEntry,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await setup_integration()

    result = await get_diagnostics_for_config_entry(hass, hass_client, config_entry)

    assert result == snapshot
