"""Tests for the Teslemetry integration."""

from unittest.mock import patch

from syrupy import SnapshotAssertion

from homeassistant.components.teslemetry.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import CONFIG

from tests.common import MockConfigEntry


async def setup_platform(hass: HomeAssistant, platforms: list[Platform] | None = None):
    """Set up the Teslemetry platform."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG,
    )
    mock_entry.add_to_hass(hass)

    if platforms is None:
        await hass.config_entries.async_setup(mock_entry.entry_id)
    else:
        with patch("homeassistant.components.teslemetry.PLATFORMS", platforms):
            await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    return mock_entry


def assert_entities(
    hass: HomeAssistant,
    entry_id: str,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all entities match their snapshot."""

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-state")


def assert_entities_alt(
    hass: HomeAssistant,
    entry_id: str,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that all entities match their alt snapshot."""
    entity_entries = er.async_entries_for_config_entry(entity_registry, entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert (state := hass.states.get(entity_entry.entity_id))
        assert state == snapshot(name=f"{entity_entry.entity_id}-statealt")
