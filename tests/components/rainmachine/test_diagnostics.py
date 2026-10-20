"""Test RainMachine diagnostics."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from regenmaschine.errors import RainMachineError
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant


async def test_entry_diagnostics(
    hass: HomeAssistant,
    config_entry,
    hass_client: ClientSessionGenerator,
    setup_rainmachine,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))


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
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    ) == snapshot(exclude=props("created_at", "modified_at"))
