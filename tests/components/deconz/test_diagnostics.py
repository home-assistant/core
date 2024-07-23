"""Test deCONZ diagnostics."""

from pydeconz.websocket import State
from syrupy import SnapshotAssertion

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .conftest import WebsocketStateType

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_setup: ConfigEntry,
    mock_websocket_state: WebsocketStateType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await mock_websocket_state(State.RUNNING)
    await hass.async_block_till_done()

    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry_setup)
        == snapshot
    )
