"""Test binary sensor for acaia integration."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


BINARY_SENSORS = ("connected", "timer_running")


async def test_binary_sensors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_scale: MagicMock,
) -> None:
    """Test the acaia binary sensors."""

    for binary_sensor in BINARY_SENSORS:
        state = hass.states.get(f"binary_sensor.lunar_123456_{binary_sensor}")
        assert state
        assert state == snapshot(name=f"state_binary_sensor_{binary_sensor}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry == snapshot(name=f"entry_binary_sensor_{binary_sensor}")
