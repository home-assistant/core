"""Tests for Ecovacs binary sensors."""

from deebot_client.events import ErrorEvent
from deebot_client.events.water_info import MopAttachedEvent
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN, Platform
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

    device = controller.devices[0]

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

    event_bus = device.events
    await notify_and_wait(hass, event_bus, MopAttachedEvent(True))

    assert (state := hass.states.get(state.entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    await notify_and_wait(hass, event_bus, MopAttachedEvent(False))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_OFF


@pytest.mark.parametrize(("device_fixture"), ["9eamof"])
async def test_water_tank_errors(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
) -> None:
    """Test water tank error binary sensors."""
    clean_entry = next(
        entry
        for entry in entity_registry.entities.values()
        if entry.translation_key == "clean_water_tank"
    )
    dirty_entry = next(
        entry
        for entry in entity_registry.entities.values()
        if entry.translation_key == "dirty_water_tank"
    )

    assert (clean_state := hass.states.get(clean_entry.entity_id))
    assert clean_state.state == STATE_UNKNOWN
    assert (dirty_state := hass.states.get(dirty_entry.entity_id))
    assert dirty_state.state == STATE_UNKNOWN

    event_bus = controller.devices[0].events

    await notify_and_wait(
        hass,
        event_bus,
        ErrorEvent(322, "Clean water tank empty or not installed"),
    )

    assert (clean_state := hass.states.get(clean_entry.entity_id))
    assert clean_state.state == STATE_ON
    assert (dirty_state := hass.states.get(dirty_entry.entity_id))
    assert dirty_state.state == STATE_OFF

    await notify_and_wait(
        hass,
        event_bus,
        ErrorEvent(323, "Dirty Water Tank is full not installed"),
    )

    assert (clean_state := hass.states.get(clean_entry.entity_id))
    assert clean_state.state == STATE_OFF
    assert (dirty_state := hass.states.get(dirty_entry.entity_id))
    assert dirty_state.state == STATE_ON

    await notify_and_wait(hass, event_bus, ErrorEvent(0, None))

    assert (clean_state := hass.states.get(clean_entry.entity_id))
    assert clean_state.state == STATE_OFF
    assert (dirty_state := hass.states.get(dirty_entry.entity_id))
    assert dirty_state.state == STATE_OFF
