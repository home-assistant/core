"""Tests for the Tedee Binary Sensors."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from pytedee_async import TedeeLock
import pytest
from syrupy import SnapshotAssertion

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import async_fire_time_changed

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


async def test_new_binary_sensors(
    hass: HomeAssistant,
    mock_tedee: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure binary sensors for new lock are added automatically."""

    for key in BINARY_SENSORS:
        state = hass.states.get(f"binary_sensor.lock_4e5f_{key}")
        assert state is None

    mock_tedee.locks_dict[666666] = TedeeLock("Lock-4E5F", 666666, 2)

    freezer.tick(timedelta(minutes=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for key in BINARY_SENSORS:
        state = hass.states.get(f"binary_sensor.lock_4e5f_{key}")
        assert state
