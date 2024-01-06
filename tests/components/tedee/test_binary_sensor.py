"""Tests for the Tedee Binary Sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")

BINARY_SENSORS = (
    "charging",
    "semi_locked",
    "pullspring_enabled",
)


async def test_binary_sensors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee battery charging sensor."""
    for key in BINARY_SENSORS:
        state = hass.states.get(f"binary_sensor.lock_1a2b_{key}")
        assert state
        assert state == snapshot(name=f"state-{key}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(name=f"entry-{key}")
