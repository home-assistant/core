"""Test RainMachine diagnostics."""

from regenmaschine.errors import RainMachineError
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_rainmachine,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


async def test_entry_diagnostics_failed_controller_diagnostics(
    hass: HomeAssistant,
    config_entry,
    controller,
    hass_client: ClientSessionGenerator,
    setup_rainmachine,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics when the controller diagnostics API call fails."""
    controller.diagnostics.current.side_effect = RainMachineError
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
