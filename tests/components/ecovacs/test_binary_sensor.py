"""Tests for Ecovacs binary sensors."""

from deebot_client.capabilities import Capabilities
from deebot_client.events import WaterAmount, WaterInfoEvent
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import STATE_OFF, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.BINARY_SENSOR


async def test_mop_attached(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
) -> None:
    """Test mop_attached binary sensor."""
    entity_id = "binary_sensor.ozmo_950_mop_attached"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    device = next(controller.devices(Capabilities))

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

    event_bus = device.events
    await notify_and_wait(
        hass, event_bus, WaterInfoEvent(WaterAmount.HIGH, mop_attached=True)
    )

    assert (state := hass.states.get(state.entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    await notify_and_wait(
        hass, event_bus, WaterInfoEvent(WaterAmount.HIGH, mop_attached=False)
    )

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_OFF
