"""Tests for the diagnostics data provided by the YouTube integration."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.youtube.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import ComponentSetup


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    setup_integration: ComponentSetup,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    await setup_integration()
    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert await get_diagnostics_for_config_entry(hass, hass_client, entry) == snapshot
