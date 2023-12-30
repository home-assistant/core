"""Tests for the Tedee Sensors."""


from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_battery(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee battery sensor."""
    state = hass.states.get("sensor.lock_1a2b_battery")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot


async def test_pullspring_duration(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee pullspring duration sensor."""
    state = hass.states.get("sensor.lock_1a2b_pullspring_duration")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry.device_id
    assert entry == snapshot

    device = device_registry.async_get(entry.device_id)
    assert device
    assert device == snapshot
