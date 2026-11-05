"""Tests for the diagnostics data provided by the Belkin WeMo integration."""

from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    wemo_entity: er.RegistryEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test config entry diagnostics."""
    config_entry = hass.config_entries.async_get_entry(wemo_entity.config_entry_id)
    assert (
        await get_diagnostics_for_config_entry(hass, hass_client, config_entry)
        == snapshot
    )
