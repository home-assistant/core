"""Tests for the diagnostics data provided by the Webmin integration."""

from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from .conftest import async_init_integration

from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    assert await get_diagnostics_for_config_entry(
        hass, hass_client, await async_init_integration(hass)
    ) == snapshot(exclude=props("created_at", "modified_at"))
