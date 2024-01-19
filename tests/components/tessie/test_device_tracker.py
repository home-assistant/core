"""Test the Tessie device tracker platform."""

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform


async def test_device_tracker(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the device tracker entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    entity_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)

    assert entity_entries
    for entity_entry in entity_entries:
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )
