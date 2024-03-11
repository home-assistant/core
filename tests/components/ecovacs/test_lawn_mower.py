"""Tests for Ecovacs lawn mower entities."""

from dataclasses import dataclass

from deebot_client.capabilities import MowerCapabilities
from deebot_client.command import Command
from deebot_client.commands.json import Charge, CleanV2
from deebot_client.events import StateEvent
from deebot_client.models import CleanAction, State
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.lawn_mower import (
    DOMAIN as PLATFORM_DOMAIN,
    LawnMowerActivity,
)
from homeassistant.components.lawn_mower.const import (
    SERVICE_DOCK,
    SERVICE_PAUSE,
    SERVICE_START_MOWING,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.LAWN_MOWER


@pytest.mark.parametrize(
    ("device_fixture"),
    [
        "5xu9h3",
    ],
)
async def test_lawn_mower(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
) -> None:
    """Test lawn mower states."""
    entity_id = "lawn_mower.goat_g1"
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    device = next(controller.devices(MowerCapabilities))

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

    event_bus = device.events
    await notify_and_wait(hass, event_bus, StateEvent(State.CLEANING))

    assert (state := hass.states.get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-state")
    assert state.state == LawnMowerActivity.MOWING

    await notify_and_wait(hass, event_bus, StateEvent(State.DOCKED))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == LawnMowerActivity.DOCKED


@dataclass(frozen=True)
class MowerTestCase:
    """Mower test."""

    command: Command
    service_name: str


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "tests"),
    [
        (
            "5xu9h3",
            "lawn_mower.goat_g1",
            [
                MowerTestCase(Charge(), SERVICE_DOCK),
                MowerTestCase(CleanV2(CleanAction.PAUSE), SERVICE_PAUSE),
                MowerTestCase(CleanV2(CleanAction.START), SERVICE_START_MOWING),
            ],
        ),
    ],
    ids=["5xu9h3"],
)
async def test_mover_services(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: list[str],
    tests: list[MowerTestCase],
) -> None:
    """Test mover services."""
    device = next(controller.devices(MowerCapabilities))

    for test in tests:
        device._execute_command.reset_mock()
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            test.service_name,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
        device._execute_command.assert_called_with(test.command)
