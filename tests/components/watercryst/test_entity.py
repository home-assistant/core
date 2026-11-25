"""Tests for WATERCryst entities."""

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.helpers import device_registry as dr, entity_registry as er


@pytest.mark.usefixtures("setup_integration")
async def test_initialization(
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test WATERCryst entity device info attributes."""
    entity_entry = entity_registry.async_get("sensor.ha_device_device_mode")

    assert entity_entry == snapshot

    device_entry = device_registry.async_get(entity_entry.device_id)

    assert device_entry == snapshot
