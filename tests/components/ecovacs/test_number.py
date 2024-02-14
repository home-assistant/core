"""Tests for Ecovacs select entities."""

from dataclasses import dataclass

from deebot_client.command import Command
from deebot_client.commands.json import SetVolume
from deebot_client.events import Event, VolumeEvent
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.number.const import (
    ATTR_VALUE,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import block_till_done

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.NUMBER


@dataclass(frozen=True)
class NumberTestCase:
    """Number test."""

    entity_id: str
    event: Event
    current_state: str
    set_value: int
    command: Command


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "tests"),
    [
        (
            "yna5x1",
            [
                NumberTestCase(
                    "number.ozmo_950_volume", VolumeEvent(5, 11), "5", 10, SetVolume(10)
                ),
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_number_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    tests: list[NumberTestCase],
) -> None:
    """Test that number entity snapshots match."""
    device = controller.devices[0]
    event_bus = device.events

    assert sorted(hass.states.async_entity_ids()) == sorted(
        test.entity_id for test in tests
    )
    for test_case in tests:
        entity_id = test_case.entity_id
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_UNKNOWN

        event_bus.notify(test_case.event)
        await block_till_done(hass, event_bus)

        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state
        assert state.state == test_case.current_state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info.did)}

        device._execute_command.reset_mock()
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: test_case.set_value},
            blocking=True,
        )
        device._execute_command.assert_called_with(test_case.command)


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            ["number.ozmo_950_volume"],
        ),
    ],
    ids=["yna5x1"],
)
async def test_disabled_by_default_number_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default number entities."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (
            entry := entity_registry.async_get(entity_id)
        ), f"Entity registry entry for {entity_id} is missing"
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_volume_maximum(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Test volume maximum."""
    device = controller.devices[0]
    event_bus = device.events
    entity_id = "number.ozmo_950_volume"
    assert (state := hass.states.get(entity_id))
    assert state.attributes["max"] == 10

    event_bus.notify(VolumeEvent(5, 20))
    await block_till_done(hass, event_bus)
    assert (state := hass.states.get(entity_id))
    assert state.state == "5"
    assert state.attributes["max"] == 20

    event_bus.notify(VolumeEvent(10, None))
    await block_till_done(hass, event_bus)
    assert (state := hass.states.get(entity_id))
    assert state.state == "10"
    assert state.attributes["max"] == 20
