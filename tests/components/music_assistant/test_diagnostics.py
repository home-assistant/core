"""Test Music Assistant diagnostics."""

from unittest.mock import MagicMock

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant

from .common import setup_integration_from_fixtures


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    music_assistant_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )


async def test_diagnostics_player_controls(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    music_assistant_client: MagicMock,
) -> None:
    """Test delegated player controls do not leak the controlling player id."""
    config_entry = await setup_integration_from_fixtures(hass, music_assistant_client)
    player = music_assistant_client.players._players["00:00:00:00:00:01"]
    player.power_control = "none"
    player.volume_control = "00:00:00:00:00:02"
    player.mute_control = "fake"

    diagnostics = await get_diagnostics_for_config_entry(
        hass, hass_client, config_entry
    )

    player_diagnostics = diagnostics["players"][0]
    assert player_diagnostics["power_control"] == "none"
    assert player_diagnostics["volume_control"] == "delegated"
    assert player_diagnostics["mute_control"] == "fake"
