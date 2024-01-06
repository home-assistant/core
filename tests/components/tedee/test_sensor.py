"""Tests for the Tedee Sensors."""


from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

pytestmark = pytest.mark.usefixtures("init_integration")


SENSORS = (
    "battery",
    "pullspring_duration",
)


async def test_sensors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test tedee sensors."""
    for key in SENSORS:
        state = hass.states.get(f"sensor.lock_1a2b_{key}")
        assert state
        assert state == snapshot(name=f"state-{key}")

        entry = entity_registry.async_get(state.entity_id)
        assert entry
        assert entry.device_id
        assert entry == snapshot(name=f"entry-{key}")
