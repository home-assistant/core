"""Tests for Ecovacs vacuum entities."""

from collections.abc import Generator
from dataclasses import asdict, replace
import logging
from unittest.mock import patch

from deebot_client.authentication import Authenticator
from deebot_client.capabilities import CapabilityNumber
from deebot_client.device import Device
from deebot_client.events import CachedMapInfoEvent, CleanCountEvent, Event, RoomsEvent
from deebot_client.events.map import Map
from deebot_client.models import CleanMode, DeviceInfo, Room
from deebot_client.rs.map import RotationAngle  # pylint: disable=no-name-in-module
import pytest
from pytest_homeassistant.typing import WebSocketGenerator

from homeassistant.components import vacuum
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .util import notify_and_wait

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


@pytest.mark.parametrize(
    (
        "device_fixture",
        "entity_id",
        "events",
        "service_options",
        "expected_cleanings",
        "expected_supported_passes",
    ),
    [
        pytest.param(
            "55uoqe", "vacuum.dbmini", [], {}, 1, [1, 2, 3, 4], id="default_count"
        ),
        pytest.param(
            "55uoqe",
            "vacuum.dbmini",
            [CleanCountEvent(2)],
            {},
            2,
            [1, 2, 3, 4],
            id="clean_count_from_device",
        ),
        pytest.param(
            "55uoqe",
            "vacuum.dbmini",
            [],
            {"passes": 4},
            4,
            [1, 2, 3, 4],
            id="explicit_four_passes",
        ),
        pytest.param(
            "55uoqe",
            "vacuum.dbmini",
            [CleanCountEvent(2)],
            {"passes": 1},
            1,
            [1, 2, 3, 4],
            id="explicit_overrides_count",
        ),
        pytest.param("qhe2o2", "vacuum.dusty", [], {}, 1, None, id="clean_v2"),
    ],
)
async def test_clean_area(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
    events: list[Event],
    service_options: dict[str, int],
    expected_cleanings: int,
    expected_supported_passes: list[int] | None,
) -> None:
    """Test clean_area service call."""
    _prepare_test(hass, entity_registry, entity_id)

    device = controller.devices[0]
    event_bus = device.events

    for event in events:
        await notify_and_wait(hass, event_bus, event)

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
            **service_options,
        },
        blocking=True,
    )

    assert device._execute_command.call_count == 1
    command = device._execute_command.call_args.args[0]
    state = hass.states.get(entity_id)
    assert state is not None
    passes_feature = vacuum.VacuumEntityFeature.CLEAN_AREA_PASSES
    expected_command = device.capabilities.clean.action.area(
        CleanMode.SPOT_AREA, [2, 1], expected_cleanings
    )
    assert command == expected_command
    assert ("clean_area_passes" in state.attributes) is (
        expected_supported_passes is not None
    )
    assert state.attributes.get("clean_area_passes") == expected_supported_passes
    assert bool(state.attributes["supported_features"] & passes_feature) is (
        expected_supported_passes is not None
    )


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("55uoqe", "vacuum.dbmini")])
async def test_clean_area_passes_override_then_omission(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """An explicit pass count must not replace the device's saved count."""
    _prepare_test(hass, entity_registry, entity_id)
    device = controller.devices[0]
    event_bus = device.events

    await notify_and_wait(hass, event_bus, CleanCountEvent(2))
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
            }
        ),
    )
    device._execute_command.reset_mock()

    for service_options in ({"passes": 4}, {}):
        await hass.services.async_call(
            vacuum.DOMAIN,
            vacuum.SERVICE_CLEAN_AREA,
            {
                ATTR_ENTITY_ID: entity_id,
                "cleaning_area_id": ["area_living_room", "area_kitchen"],
                **service_options,
            },
            blocking=True,
        )

    assert device._execute_command.call_count == 2
    first_command, second_command = (
        call.args[0] for call in device._execute_command.call_args_list
    )
    assert first_command == device.capabilities.clean.action.area(
        CleanMode.SPOT_AREA, [2, 1], 4
    )
    assert second_command == device.capabilities.clean.action.area(
        CleanMode.SPOT_AREA, [2, 1], 2
    )


class TestCleanAreaPassesCapabilityBounds:
    """Exercise model-specific count bounds through the registered vacuum."""

    @pytest.fixture(autouse=True)
    def bounded_device(self, minimum: int, maximum: int) -> Generator[None]:
        """Supply bounded capabilities before integration setup and entity creation."""

        def create_device(info: DeviceInfo, authenticator: Authenticator) -> Device:
            count = info.static.capabilities.clean.count
            assert count is not None
            bounded_count = CapabilityNumber(
                event=count.event,
                get=count.get,
                set=count.set,
                min=minimum,
                max=maximum,
            )
            bounded_caps = replace(
                info.static.capabilities,
                clean=replace(info.static.capabilities.clean, count=bounded_count),
            )
            bounded_info = replace(
                info, static=replace(info.static, capabilities=bounded_caps)
            )
            return Device(bounded_info, authenticator)

        with patch(
            "homeassistant.components.ecovacs.controller.Device",
            side_effect=create_device,
        ):
            yield

    @pytest.mark.parametrize(
        ("minimum", "maximum", "expected", "invalid"),
        [(1, 2, [1, 2], 3), (2, 4, [2, 3, 4], 1)],
    )
    @pytest.mark.parametrize("device_fixture", ["55uoqe"])
    async def test_clean_area_passes_capability_bounds(
        self,
        hass: HomeAssistant,
        entity_registry: er.EntityRegistry,
        controller: EcovacsController,
        minimum: int,
        maximum: int,
        expected: list[int],
        invalid: int,
    ) -> None:
        """Publish literal bounds and reject out-of-range calls before dispatch."""
        entity_id = "vacuum.dbmini"
        _prepare_test(hass, entity_registry, entity_id)
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.attributes["clean_area_passes"] == expected
        assert state.attributes["supported_features"] & (
            vacuum.VacuumEntityFeature.CLEAN_AREA_PASSES
        )

        device = controller.devices[0]
        device._execute_command.reset_mock()
        with pytest.raises(ServiceValidationError) as exc_info:
            await hass.services.async_call(
                vacuum.DOMAIN,
                vacuum.SERVICE_CLEAN_AREA,
                {
                    ATTR_ENTITY_ID: entity_id,
                    "cleaning_area_id": ["area_kitchen"],
                    "passes": invalid,
                },
                blocking=True,
            )
        assert exc_info.value.translation_key == "clean_area_passes_unsupported"
        device._execute_command.assert_not_called()

        await notify_and_wait(
            hass,
            device.events,
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
        )
        device._execute_command.reset_mock()
        await hass.services.async_call(
            vacuum.DOMAIN,
            vacuum.SERVICE_CLEAN_AREA,
            {
                ATTR_ENTITY_ID: entity_id,
                "cleaning_area_id": ["area_kitchen"],
                "passes": 2,
            },
            blocking=True,
        )
        device._execute_command.assert_called_once()
        command = device._execute_command.call_args.args[0]
        assert command == device.capabilities.clean.action.area(
            CleanMode.SPOT_AREA, [1], 2
        )


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("qhe2o2", "vacuum.dusty")])
async def test_clean_area_passes_not_supported_by_command(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Reject passes when the area command does not transmit a count."""
    _prepare_test(hass, entity_registry, entity_id)
    state = hass.states.get(entity_id)
    assert state is not None
    assert "clean_area_passes" not in state.attributes
    assert not state.attributes["supported_features"] & (
        vacuum.VacuumEntityFeature.CLEAN_AREA_PASSES
    )

    device = controller.devices[0]
    assert device.capabilities.clean.count is not None
    device._execute_command.reset_mock()

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            vacuum.DOMAIN,
            vacuum.SERVICE_CLEAN_AREA,
            {
                ATTR_ENTITY_ID: entity_id,
                "cleaning_area_id": ["area_living_room"],
                "passes": 4,
            },
            blocking=True,
        )

    assert exc_info.value.translation_key == "clean_area_passes_unsupported"
    device._execute_command.assert_not_called()


@pytest.mark.parametrize(("device_fixture", "entity_id"), [("55uoqe", "vacuum.dbmini")])
async def test_clean_area_unsupported_passes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Reject a pass count outside the Ecovacs supported range."""
    _prepare_test(hass, entity_registry, entity_id)
    device = controller.devices[0]
    device._execute_command.reset_mock()

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            vacuum.DOMAIN,
            vacuum.SERVICE_CLEAN_AREA,
            {
                ATTR_ENTITY_ID: entity_id,
                "cleaning_area_id": ["area_living_room"],
                "passes": 5,
            },
            blocking=True,
        )

    device._execute_command.assert_not_called()


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
            "No valid segments to clean after validation,"
            " skipping clean segments command",
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
            'Map "Second map" is not currently selected,'
            ' skipping segment "Bedroom" (1)',
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
    issue_registry: ir.IssueRegistry,
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
    issue_id = f"segments_changed_{entity_entry.id}"
    issue = issue_registry.async_get_issue(vacuum.DOMAIN, issue_id)
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
