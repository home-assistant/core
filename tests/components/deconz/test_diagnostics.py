"""Test deCONZ diagnostics."""

from pydeconz.websocket import State
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .conftest import WebsocketStateType


async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    config_entry_setup: MockConfigEntry,
    mock_websocket_state: WebsocketStateType,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    await mock_websocket_state(State.RUNNING)
    await hass.async_block_till_done()

    assert await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry_setup
    ) == snapshot(exclude=props("created_at", "modified_at"))
