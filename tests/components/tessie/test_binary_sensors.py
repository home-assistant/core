"""Test the Tessie binary sensor platform."""
from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_binary_sensors(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the binary sensor entities are correct."""

    entry = await setup_platform(hass, [Platform.BINARY_SENSOR])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
