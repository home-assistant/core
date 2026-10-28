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
