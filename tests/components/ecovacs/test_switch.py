"""Tests for Ecovacs select entities."""

from dataclasses import dataclass

from deebot_client.command import Command
from deebot_client.commands.json import (
    SetAdvancedMode,
    SetCarpetAutoFanBoost,
    SetContinuousCleaning,
)
from deebot_client.events import (
    AdvancedModeEvent,
    CarpetAutoFanBoostEvent,
    ContinuousCleaningEvent,
    Event,
)
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.switch.const import DOMAIN as PLATFORM_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import block_till_done

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.SWITCH


@dataclass(frozen=True)
class SwitchTestCase:
    """Switch test."""

    entity_id: str
    event: Event
    command: type[Command]


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "tests"),
    [
        (
            "yna5x1",
            [
                SwitchTestCase(
                    "switch.ozmo_950_advanced_mode",
                    AdvancedModeEvent(True),
                    SetAdvancedMode,
                ),
                SwitchTestCase(
                    "switch.ozmo_950_continuous_cleaning",
                    ContinuousCleaningEvent(True),
                    SetContinuousCleaning,
                ),
                SwitchTestCase(
                    "switch.ozmo_950_carpet_auto_boost_suction",
                    CarpetAutoFanBoostEvent(True),
                    SetCarpetAutoFanBoost,
                ),
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_switch_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    tests: list[SwitchTestCase],
) -> None:
    """Test switch entities."""
    device = controller.devices[0]
    event_bus = device.events

    assert hass.states.async_entity_ids() == [test.entity_id for test in tests]
    for test_case in tests:
        entity_id = test_case.entity_id
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_OFF

        event_bus.notify(test_case.event)
        await block_till_done(hass, event_bus)

        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state
        assert state.state == STATE_ON

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info.did)}

        device._execute_command.reset_mock()
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(test_case.command(False))

        device._execute_command.reset_mock()
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(test_case.command(True))


@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "switch.ozmo_950_advanced_mode",
                "switch.ozmo_950_continuous_cleaning",
                "switch.ozmo_950_carpet_auto_boost_suction",
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_disabled_by_default_switch_entities(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, entity_ids: list[str]
) -> None:
    """Test the disabled by default switch entities."""
    for entity_id in entity_ids:
        assert not hass.states.get(entity_id)

        assert (
            entry := entity_registry.async_get(entity_id)
        ), f"Entity registry entry for {entity_id} is missing"
        assert entry.disabled
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION
