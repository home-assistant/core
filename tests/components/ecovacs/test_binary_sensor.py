"""Tests for Ecovacs binary sensors."""

from deebot_client.event_bus import EventBus
from deebot_client.events import WaterAmount, WaterInfoEvent
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import STATE_OFF, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


async def test_mop_attached(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    snapshot: SnapshotAssertion,
) -> None:
    """Test mop_attached binary sensor."""
    entity_id = "binary_sensor.ozmo_950_mop_attached"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    event_bus: EventBus = controller.devices[0].events
    await notify_and_wait(
        hass, event_bus, WaterInfoEvent(WaterAmount.HIGH, mop_attached=True)
    )

    assert (state := hass.states.get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-state")

    await notify_and_wait(
        hass, event_bus, WaterInfoEvent(WaterAmount.HIGH, mop_attached=False)
    )

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_OFF
