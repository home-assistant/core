"""Test the Tessie device tracker platform."""

from syrupy import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import assert_entities, setup_platform


async def test_device_tracker(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Tests that the device tracker entities are correct."""

    entry = await setup_platform(hass, [Platform.DEVICE_TRACKER])

    assert_entities(hass, entry.entry_id, entity_registry, snapshot)
