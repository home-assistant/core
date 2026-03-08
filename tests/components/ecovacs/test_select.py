"""Tests for Ecovacs select entities."""

from deebot_client.command import Command
from deebot_client.commands.json import SetWaterInfo
from deebot_client.commands.json.auto_empty import SetAutoEmpty
from deebot_client.event_bus import EventBus
from deebot_client.events import auto_empty
from deebot_client.events.map import CachedMapInfoEvent, MajorMapEvent, Map
from deebot_client.events.water_info import WaterAmount, WaterAmountEvent
from deebot_client.events.work_mode import WorkMode, WorkModeEvent
from deebot_client.rs.map import RotationAngle  # pylint: disable=no-name-in-module
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import select
from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import block_till_done

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.SELECT


async def notify_events(hass: HomeAssistant, event_bus: EventBus):
    """Notify events."""
    event_bus.notify(WaterAmountEvent(WaterAmount.ULTRAHIGH))
    event_bus.notify(WorkModeEvent(WorkMode.VACUUM))
    event_bus.notify(
        CachedMapInfoEvent(
            {
                Map(
                    id="1", name="", using=False, built=False, angle=RotationAngle.DEG_0
                ),
                Map(
                    id="2",
                    name="Map 2",
                    using=True,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
            }
        )
    )
    event_bus.notify(MajorMapEvent("2", [], requested=False))
    event_bus.notify(auto_empty.AutoEmptyEvent(True, auto_empty.Frequency.AUTO))
    await block_till_done(hass, event_bus)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "entity_ids"),
    [
        (
            "yna5x1",
            [
                "select.ozmo_950_water_flow_level",
                "select.ozmo_950_active_map",
            ],
        ),
        (
            "qhe2o2",
            [
                "select.dusty_water_flow_level",
                "select.dusty_auto_empty_frequency",
                "select.dusty_active_map",
            ],
        ),
        (
            "n0vyif",
            [
                "select.x8_pro_omni_work_mode",
                "select.x8_pro_omni_auto_empty_frequency",
                "select.x8_pro_omni_active_map",
            ],
        ),
    ],
)
async def test_selects(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    entity_ids: list[str],
) -> None:
    """Test that select entity snapshots match."""
    assert hass.states.async_entity_ids() == entity_ids
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert state.state == STATE_UNKNOWN

    device = controller.devices[0]
    await notify_events(hass, device.events)
    for entity_id in entity_ids:
        assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
        assert snapshot(name=f"{entity_id}:state") == state

        assert (entity_entry := entity_registry.async_get(state.entity_id))
        assert snapshot(name=f"{entity_id}:entity-registry") == entity_entry

        assert entity_entry.device_id
        assert (device_entry := device_registry.async_get(entity_entry.device_id))
        assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "current_state", "set_state", "command"),
    [
        (
            "yna5x1",
            "select.ozmo_950_water_flow_level",
            "ultrahigh",
            "low",
            SetWaterInfo(WaterAmount.LOW),
        ),
        (
            "qhe2o2",
            "select.dusty_auto_empty_frequency",
            "auto",
            "smart",
            SetAutoEmpty(None, auto_empty.Frequency.SMART),
        ),
    ],
)
async def test_selects_change(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: list[str],
    current_state: str,
    set_state: str,
    command: Command,
) -> None:
    """Test that changing select entities works."""
    device = controller.devices[0]
    await notify_events(hass, device.events)

    assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
    assert state.state == current_state

    device._execute_command.reset_mock()
    await hass.services.async_call(
        select.DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: set_state},
        blocking=True,
    )
    device._execute_command.assert_called_with(command)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["n0vyif"])
async def test_work_mode_intelligent_hosting_local_only(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Test that selecting intelligent_hosting stores state locally without a robot command."""
    entity_id = "select.x8_pro_omni_work_mode"
    device = controller.devices[0]
    await notify_events(hass, device.events)

    assert (state := hass.states.get(entity_id)), f"State of {entity_id} is missing"
    assert state.state == "vacuum"

    device._execute_command.reset_mock()
    await hass.services.async_call(
        select.DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "intelligent_hosting"},
        blocking=True,
    )
    # intelligent_hosting is stored locally in HA only — no command sent to robot
    device._execute_command.assert_not_called()
    assert (
        state := hass.states.get(entity_id)
    ), f"State of {entity_id} is missing after option change"
    assert state.state == "intelligent_hosting"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["n0vyif"])
async def test_work_mode_switch_from_intelligent_hosting_updates_state(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Test that switching from intelligent_hosting to a real mode updates state immediately.

    When intelligent_hosting is set (local-only), the robot's actual mode is unchanged.
    Switching back to a real mode (e.g. vacuum) sends setWorkMode to the robot. If the
    robot was already in that mode it won't fire a WorkModeEvent, so the state must be
    updated optimistically to avoid the dropdown appearing stuck.
    """
    entity_id = "select.x8_pro_omni_work_mode"
    device = controller.devices[0]
    await notify_events(hass, device.events)

    # Set intelligent_hosting locally
    await hass.services.async_call(
        select.DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "intelligent_hosting"},
        blocking=True,
    )
    assert hass.states.get(entity_id).state == "intelligent_hosting"

    # Switch back to a real work mode — state must update immediately (optimistic),
    # even if no WorkModeEvent is fired (robot was already in that mode).
    await hass.services.async_call(
        select.DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "vacuum"},
        blocking=True,
    )
    # Command is sent to the robot
    assert device._execute_command.call_count == 1
    # State is updated immediately without waiting for a robot event
    assert hass.states.get(entity_id).state == "vacuum"
