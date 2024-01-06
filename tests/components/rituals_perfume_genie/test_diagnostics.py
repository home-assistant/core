"""Tests for the diagnostics data provided by the Rituals Perfume Genie integration."""
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import init_integration, mock_config_entry, mock_diffuser

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    config_entry = mock_config_entry(unique_id="number_test")
    diffuser = mock_diffuser(hublot="lot123", perfume_amount=2)
    await init_integration(hass, config_entry, [diffuser])

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
