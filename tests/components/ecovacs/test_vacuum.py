"""Tests for Ecovacs vacuum entities."""

from dataclasses import asdict
import logging

from deebot_client.commands.json.custom import CustomCommand
from deebot_client.events import CachedMapInfoEvent, Event, RoomsEvent
from deebot_client.events.map import Map
from deebot_client.events.work_mode import WorkMode, WorkModeEvent
from deebot_client.models import CleanAction, CleanMode, Room
from deebot_client.rs.map import RotationAngle  # pylint: disable=no-name-in-module
import pytest

from homeassistant.components import select, vacuum
from homeassistant.components.ecovacs.const import INTELLIGENT_HOSTING
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_OPTION,
    SERVICE_SELECT_OPTION,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .util import notify_and_wait

from tests.typing import WebSocketGenerator

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.VACUUM


def _prepare_test(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    entity_id: str,
) -> None:
    entity_registry.async_update_entity_options(
        entity_id,
        vacuum.DOMAIN,
        {
            "area_mapping": {
                "area_kitchen": ["1_1"],
                "area_living_room": ["1_2"],
                "area_bedroom": ["2_1"],
            },
            "last_seen_segments": [
                {"id": "1_1", "name": "Kitchen", "group": "Main map"},
                {"id": "1_2", "name": "Living room", "group": "Main map"},
                {"id": "2_1", "name": "Bedroom", "group": "Second map"},
            ],
        },
    )

    vacuum_obj = hass.data[vacuum.DATA_COMPONENT].get_entity(entity_id)
    assert vacuum_obj.last_seen_segments == [
        vacuum.Segment(id="1_1", name="Kitchen", group="Main map"),
        vacuum.Segment(id="1_2", name="Living room", group="Main map"),
        vacuum.Segment(id="2_1", name="Bedroom", group="Second map"),
    ]
    assert vacuum_obj.supported_features & vacuum.VacuumEntityFeature.CLEAN_AREA


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_clean_area(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test clean_area service call."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    event_bus = device.events

    await notify_and_wait(
        hass,
        event_bus,
        CachedMapInfoEvent(
            {
                Map(
                    id="1",
                    name="Main map",
                    using=True,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
                Map(
                    id="2",
                    name="Second map",
                    using=False,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
            }
        ),
    )

    device._execute_command.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_CLEAN_AREA,
        {
            ATTR_ENTITY_ID: entity_id,
            "cleaning_area_id": ["area_living_room", "area_kitchen"],
        },
        blocking=True,
    )

    assert device._execute_command.call_count == 1
    command = device._execute_command.call_args.args[0]
    expected_command = device.capabilities.clean.action.area(
        CleanMode.SPOT_AREA, [2, 1], 1
    )
    assert command == expected_command


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_clean_area_no_map(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test clean_area service call logs warning when no map info is available."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    device._execute_command.reset_mock()

    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_CLEAN_AREA,
        {
            ATTR_ENTITY_ID: entity_id,
            "cleaning_area_id": ["area_living_room", "area_kitchen"],
        },
        blocking=True,
    )
    assert caplog.record_tuples == [
        (
            "homeassistant.components.ecovacs.vacuum",
            logging.WARNING,
            "No map information available, cannot clean segments",
        ),
    ]
    assert device._execute_command.call_count == 0


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_clean_area_invalid_map_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test clean_area service call logs warning when invalid map ID is provided."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    event_bus = device.events
    await notify_and_wait(
        hass,
        event_bus,
        CachedMapInfoEvent(
            {
                Map(
                    id="2",
                    name="Second map",
                    using=False,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
            }
        ),
    )
    device._execute_command.reset_mock()
    caplog.clear()

    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_CLEAN_AREA,
        {
            ATTR_ENTITY_ID: entity_id,
            "cleaning_area_id": ["area_living_room", "area_kitchen"],
        },
        blocking=True,
    )

    assert caplog.record_tuples == [
        (
            "homeassistant.components.ecovacs.vacuum",
            logging.WARNING,
            "Map ID 1 not found in available maps",
        ),
        # twice as both areas reference the same missing map ID
        (
            "homeassistant.components.ecovacs.vacuum",
            logging.WARNING,
            "Map ID 1 not found in available maps",
        ),
        (
            "homeassistant.components.ecovacs.vacuum",
            logging.WARNING,
            "No valid segments to clean after validation, skipping clean segments command",
        ),
    ]
    assert device._execute_command.call_count == 0


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_clean_area_room_from_not_current_map(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    caplog: pytest.LogCaptureFixture,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test clean_area service call logs warning when room is from a not current map."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    event_bus = device.events
    await notify_and_wait(
        hass,
        event_bus,
        CachedMapInfoEvent(
            {
                Map(
                    id="1",
                    name="Main map",
                    using=True,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
                Map(
                    id="2",
                    name="Second map",
                    using=False,
                    built=True,
                    angle=RotationAngle.DEG_0,
                ),
            }
        ),
    )

    await notify_and_wait(
        hass,
        event_bus,
        RoomsEvent(
            map_id="1",
            rooms=[
                Room(name="Kitchen", id=1, coordinates=""),
                Room(name="Living room", id=2, coordinates=""),
            ],
        ),
    )
    device._execute_command.reset_mock()
    caplog.clear()

    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_CLEAN_AREA,
        {
            ATTR_ENTITY_ID: entity_id,
            "cleaning_area_id": ["area_bedroom", "area_kitchen"],
        },
        blocking=True,
    )

    assert caplog.record_tuples == [
        (
            "homeassistant.components.ecovacs.vacuum",
            logging.WARNING,
            'Map "Second map" is not currently selected, skipping segment "Bedroom" (1)',
        ),
    ]
    assert device._execute_command.call_count == 1
    command = device._execute_command.call_args.args[0]
    expected_command = device.capabilities.clean.action.area(
        CleanMode.SPOT_AREA, [1], 1
    )
    assert command == expected_command


@pytest.mark.parametrize(
    "events",
    [
        (
            CachedMapInfoEvent(
                {
                    Map(
                        id="1",
                        name="Main map",
                        using=True,
                        built=True,
                        angle=RotationAngle.DEG_0,
                    ),
                    Map(
                        id="2",
                        name="Second map",
                        using=False,
                        built=True,
                        angle=RotationAngle.DEG_0,
                    ),
                }
            ),
            RoomsEvent(
                map_id="1",
                rooms=[
                    Room(name="Kitchen", id=1, coordinates=""),
                ],
            ),
        ),
        (
            CachedMapInfoEvent(
                {
                    Map(
                        id="1",
                        name="Main map",
                        using=True,
                        built=True,
                        angle=RotationAngle.DEG_0,
                    ),
                }
            ),
            RoomsEvent(
                map_id="1",
                rooms=[
                    Room(name="Kitchen", id=1, coordinates=""),
                    Room(name="Living room", id=2, coordinates=""),
                ],
            ),
        ),
        (
            CachedMapInfoEvent(
                {
                    Map(
                        id="1",
                        name="Main map",
                        using=True,
                        built=True,
                        angle=RotationAngle.DEG_0,
                    ),
                    Map(
                        id="2",
                        name="Second map",
                        using=False,
                        built=True,
                        angle=RotationAngle.DEG_0,
                    ),
                }
            ),
            RoomsEvent(
                map_id="1",
                rooms=[
                    Room(name="Kitchen", id=1, coordinates=""),
                    Room(name="Living room", id=2, coordinates=""),
                    Room(name="Bedroom", id=3, coordinates=""),
                ],
            ),
        ),
    ],
    ids=[
        "room removed",
        "map removed",
        "room added",
    ],
)
@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_raise_segment_changed_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
    events: tuple[Event, ...],
) -> None:
    """Test that the issue is raised on segment changes."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    event_bus = device.events

    for event in events:
        await notify_and_wait(hass, event_bus, event)

    entity_entry = entity_registry.async_get(entity_id)
    issue_id = f"{vacuum.ISSUE_SEGMENTS_CHANGED}_{entity_entry.id}"
    issue = ir.async_get(hass).async_get_issue(vacuum.DOMAIN, issue_id)
    assert issue is not None


@pytest.mark.parametrize(
    ("events", "expected_segments", "expected_log_messages"),
    [
        ((), [], []),
        (
            (
                CachedMapInfoEvent(
                    {
                        Map(
                            id="1",
                            name="Main map",
                            using=True,
                            built=True,
                            angle=RotationAngle.DEG_0,
                        ),
                    }
                ),
                RoomsEvent(
                    map_id="2",
                    rooms=[
                        Room(name="Kitchen", id=1, coordinates=""),
                        Room(name="Living room", id=2, coordinates=""),
                    ],
                ),
            ),
            [],
            [
                (
                    "homeassistant.components.ecovacs.vacuum",
                    logging.WARNING,
                    "Map ID 2 not found in available maps",
                )
            ],
        ),
        (
            (
                CachedMapInfoEvent(
                    {
                        Map(
                            id="1",
                            name="Main map",
                            using=True,
                            built=True,
                            angle=RotationAngle.DEG_0,
                        ),
                    }
                ),
                RoomsEvent(
                    map_id="1",
                    rooms=[
                        Room(name="Kitchen", id=1, coordinates=""),
                        Room(name="Living room", id=2, coordinates=""),
                    ],
                ),
            ),
            [
                vacuum.Segment(id="1_1", name="Kitchen", group="Main map"),
                vacuum.Segment(id="1_2", name="Living room", group="Main map"),
            ],
            [],
        ),
    ],
    ids=[
        "no room event available",
        "invalid map ID in room event",
        "room added",
    ],
)
@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_get_segments(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
    caplog: pytest.LogCaptureFixture,
    controller: EcovacsController,
    entity_id: str,
    events: tuple[Event, ...],
    expected_segments: list[vacuum.Segment],
    expected_log_messages: list[tuple[str, int, str]],
) -> None:
    """Test vacuum/get_segments websocket command."""
    device = controller.devices[0]
    event_bus = device.events

    for event in events:
        await notify_and_wait(hass, event_bus, event)

    caplog.clear()

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity_id}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"segments": [asdict(seg) for seg in expected_segments]}
    for log_message in expected_log_messages:
        assert log_message in caplog.record_tuples


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["n0vyif"])
@pytest.mark.parametrize("platforms", [[Platform.SELECT, Platform.VACUUM]])
async def test_start_intelligent_hosting_sends_entrust_command(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Test that vacuum.start sends clean_V2/entrust when intelligent_hosting is selected."""
    vacuum_entity_id = "vacuum.x8_pro_omni"
    work_mode_entity_id = "select.x8_pro_omni_work_mode"
    device = controller.devices[0]

    # Set the work mode to intelligent_hosting (local-only, no robot command)
    await hass.services.async_call(
        select.DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: work_mode_entity_id, ATTR_OPTION: INTELLIGENT_HOSTING},
        blocking=True,
    )
    assert hass.states.get(work_mode_entity_id).state == INTELLIGENT_HOSTING

    device._execute_command.reset_mock()

    # Start the vacuum — should send clean_V2 with type: entrust
    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_START,
        {ATTR_ENTITY_ID: vacuum_entity_id},
        blocking=True,
    )
    device._execute_command.assert_called_once_with(
        CustomCommand("clean_V2", {"act": "start", "content": {"type": "entrust"}})
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
@pytest.mark.parametrize("device_fixture", ["n0vyif"])
@pytest.mark.parametrize("platforms", [[Platform.SELECT, Platform.VACUUM]])
async def test_start_normal_work_mode_sends_clean_action(
    hass: HomeAssistant,
    controller: EcovacsController,
) -> None:
    """Test that vacuum.start sends CleanAction.START when a normal work mode is selected."""
    vacuum_entity_id = "vacuum.x8_pro_omni"
    work_mode_entity_id = "select.x8_pro_omni_work_mode"
    device = controller.devices[0]

    # Set a normal work mode (sends setWorkMode to the robot)
    device.events.notify(WorkModeEvent(WorkMode.VACUUM))
    await hass.async_block_till_done()
    assert hass.states.get(work_mode_entity_id).state == "vacuum"

    device._execute_command.reset_mock()

    # Start the vacuum — should use the standard clean action
    await hass.services.async_call(
        vacuum.DOMAIN,
        vacuum.SERVICE_START,
        {ATTR_ENTITY_ID: vacuum_entity_id},
        blocking=True,
    )
    device._execute_command.assert_called_once_with(
        device.capabilities.clean.action.command(CleanAction.START)
    )
