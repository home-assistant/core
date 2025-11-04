"""Tests for Ecovacs vacuum entities."""

from dataclasses import dataclass
from typing import Any
from unittest.mock import Mock

from deebot_client.command import Command
from deebot_client.commands.json import Charge, CleanV2, PlaySound
from deebot_client.events import FanSpeedEvent, RoomsEvent, StateEvent
from deebot_client.models import CleanAction, Room, State
import pytest
from syrupy.assertion import SnapshotAssertion
import sucks

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.components.vacuum import (
    ATTR_FAN_SPEED,
    DOMAIN as PLATFORM_DOMAIN,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
    VacuumActivity,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .util import notify_and_wait

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.fixture
def platforms() -> Platform | list[Platform]:
    """Platforms, which should be loaded during the test."""
    return Platform.VACUUM


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
        ("qhe2o2", "vacuum.dusty"),
    ],
    ids=["yna5x1", "qhe2o2"],
)
async def test_vacuum(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum states."""
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")
    assert entity_entry.device_id

    device = controller.devices[0]

    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, device.device_info["did"])}

    event_bus = device.events
    await notify_and_wait(hass, event_bus, StateEvent(State.CLEANING))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.CLEANING

    await notify_and_wait(hass, event_bus, StateEvent(State.DOCKED))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.DOCKED

    await notify_and_wait(hass, event_bus, StateEvent(State.RETURNING))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.RETURNING

    await notify_and_wait(hass, event_bus, StateEvent(State.PAUSED))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.PAUSED

    await notify_and_wait(hass, event_bus, StateEvent(State.ERROR))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.ERROR

    await notify_and_wait(hass, event_bus, StateEvent(State.IDLE))

    assert (state := hass.states.get(state.entity_id))
    assert state.state == VacuumActivity.IDLE


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_fan_speed(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum fan speed."""
    assert (state := hass.states.get(entity_id))
    assert state.attributes.get(ATTR_FAN_SPEED) is None

    device = controller.devices[0]
    event_bus = device.events
    await notify_and_wait(hass, event_bus, FanSpeedEvent("normal"))

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_FAN_SPEED] == "normal"

    await notify_and_wait(hass, event_bus, FanSpeedEvent("max"))

    assert (state := hass.states.get(entity_id))
    assert state.attributes[ATTR_FAN_SPEED] == "max"


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_rooms(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum rooms attribute."""
    assert (state := hass.states.get(entity_id))
    assert state.attributes.get("rooms") == {}

    device = controller.devices[0]
    event_bus = device.events
    rooms = [
        Room(id=1, name="Living Room"),
        Room(id=2, name="Kitchen"),
        Room(id=3, name="Living Room"),  # Duplicate name
    ]
    await notify_and_wait(hass, event_bus, RoomsEvent(rooms))

    assert (state := hass.states.get(entity_id))
    rooms_attr = state.attributes["rooms"]
    assert rooms_attr["living_room"] == [1, 3]
    assert rooms_attr["kitchen"] == 2


@dataclass(frozen=True)
class VacuumServiceTestCase:
    """Vacuum service test case."""

    service_name: str
    service_data: dict[str, Any]
    expected_command: Command


@pytest.mark.parametrize(
    ("device_fixture", "entity_id", "tests"),
    [
        (
            "yna5x1",
            "vacuum.ozmo_950",
            [
                VacuumServiceTestCase(
                    SERVICE_START,
                    {},
                    CleanV2(CleanAction.START),
                ),
                VacuumServiceTestCase(
                    SERVICE_PAUSE,
                    {},
                    CleanV2(CleanAction.PAUSE),
                ),
                VacuumServiceTestCase(
                    SERVICE_STOP,
                    {},
                    CleanV2(CleanAction.STOP),
                ),
                VacuumServiceTestCase(
                    SERVICE_RETURN_TO_BASE,
                    {},
                    Charge(),
                ),
                VacuumServiceTestCase(
                    SERVICE_LOCATE,
                    {},
                    PlaySound(),
                ),
            ],
        ),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_services(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
    tests: list[VacuumServiceTestCase],
) -> None:
    """Test vacuum services."""
    device = controller.devices[0]

    for test in tests:
        device._execute_command.reset_mock()
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            test.service_name,
            {ATTR_ENTITY_ID: entity_id, **test.service_data},
            blocking=True,
        )
        device._execute_command.assert_called_with(test.expected_command)


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_set_fan_speed(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum set fan speed service."""
    device = controller.devices[0]

    device._execute_command.reset_mock()
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: "max"},
        blocking=True,
    )
    assert device._execute_command.called


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_send_command(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum send command service."""
    device = controller.devices[0]

    # Test custom command
    device._execute_command.reset_mock()
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SEND_COMMAND,
        {
            ATTR_ENTITY_ID: entity_id,
            "command": "custom_command",
            "params": {"param1": "value1"},
        },
        blocking=True,
    )
    assert device._execute_command.called


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_send_command_list_params_error(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Test vacuum send command with list params raises error."""
    with pytest.raises(
        ServiceValidationError,
        match="Params must be a dictionary",
    ):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: entity_id,
                "command": "custom_command",
                "params": ["value1", "value2"],
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_send_command_spot_area_no_params(
    hass: HomeAssistant,
    entity_id: str,
) -> None:
    """Test vacuum send command spot_area without params raises error."""
    with pytest.raises(
        ServiceValidationError,
        match="Params are required",
    ):
        await hass.services.async_call(
            PLATFORM_DOMAIN,
            SERVICE_SEND_COMMAND,
            {
                ATTR_ENTITY_ID: entity_id,
                "command": "spot_area",
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    ("device_fixture", "entity_id"),
    [
        ("yna5x1", "vacuum.ozmo_950"),
    ],
    ids=["yna5x1"],
)
async def test_vacuum_raw_get_positions_not_supported(
    hass: HomeAssistant,
    controller: EcovacsController,
    entity_id: str,
) -> None:
    """Test vacuum raw_get_positions when map capability is missing."""
    device = controller.devices[0]

    # Mock map capability to be None to trigger error
    original_map = device.capabilities.map
    device.capabilities.map = None

    try:
        with pytest.raises(
            ServiceValidationError,
            match="not supported",
        ):
            await hass.services.async_call(
                DOMAIN,
                "raw_get_positions",
                {ATTR_ENTITY_ID: entity_id},
                blocking=True,
                return_response=True,
            )
    finally:
        # Restore original value
        device.capabilities.map = original_map


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum entity."""
    entity_id = "vacuum.deebot_n79"

    assert (state := hass.states.get(entity_id))
    assert state == snapshot(name=f"{entity_id}-state")

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot(name=f"{entity_id}-entity_entry")

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry.identifiers == {(DOMAIN, "E1234567890000000003")}


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum_states(
    hass: HomeAssistant,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum state changes."""
    entity_id = "vacuum.deebot_n79"

    # Test cleaning state
    mock_vacbot.is_cleaning = True
    mock_vacbot.is_charging = False
    mock_vacbot.vacuum_status = sucks.CLEAN_MODE_AUTO
    mock_vacbot.statusEvents.notify("status")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == VacuumActivity.CLEANING

    # Test docked state
    mock_vacbot.is_cleaning = False
    mock_vacbot.is_charging = True
    mock_vacbot.statusEvents.notify("status")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == VacuumActivity.DOCKED

    # Test idle state
    mock_vacbot.is_cleaning = False
    mock_vacbot.is_charging = False
    mock_vacbot.vacuum_status = sucks.CLEAN_MODE_STOP
    mock_vacbot.statusEvents.notify("status")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == VacuumActivity.IDLE

    # Test returning state
    mock_vacbot.vacuum_status = sucks.CHARGE_MODE_RETURNING
    mock_vacbot.statusEvents.notify("status")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == VacuumActivity.RETURNING


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum_error_handling(
    hass: HomeAssistant,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum error handling."""
    entity_id = "vacuum.deebot_n79"

    # Test error state
    mock_vacbot.errorEvents.notify("Error: Wheel stuck")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.state == VacuumActivity.ERROR
    assert state.attributes["error"] == "Error: Wheel stuck"

    # Test error cleared
    mock_vacbot.errorEvents.notify("no_error")
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (state := hass.states.get(entity_id))
    assert state.attributes["error"] is None


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum_services(
    hass: HomeAssistant,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum services."""
    entity_id = "vacuum.deebot_n79"

    # Test start
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_START,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_vacbot.run.called

    # Test stop
    mock_vacbot.run.reset_mock()
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_STOP,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_vacbot.run.called

    # Test return to base
    mock_vacbot.run.reset_mock()
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_RETURN_TO_BASE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_vacbot.run.called

    # Test locate
    mock_vacbot.run.reset_mock()
    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_LOCATE,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert mock_vacbot.run.called


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum_set_fan_speed(
    hass: HomeAssistant,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum set fan speed."""
    entity_id = "vacuum.deebot_n79"

    mock_vacbot.clean_status = sucks.CLEAN_MODE_AUTO
    mock_vacbot.is_cleaning = True
    mock_vacbot.vacuum_status = sucks.CLEAN_MODE_AUTO
    mock_vacbot.statusEvents.notify("status")
    await hass.async_block_till_done(wait_background_tasks=True)

    await hass.services.async_call(
        PLATFORM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: entity_id, ATTR_FAN_SPEED: sucks.FAN_SPEED_HIGH},
        blocking=True,
    )
    assert mock_vacbot.run.called


@pytest.mark.usefixtures("mock_vacbot", "init_integration")
@pytest.mark.parametrize(
    ("device_fixture"),
    ["123"],
    ids=["123"],
)
async def test_legacy_vacuum_raw_get_positions_not_supported(
    hass: HomeAssistant,
    mock_vacbot: Mock,
) -> None:
    """Test legacy vacuum raw_get_positions raises error."""
    entity_id = "vacuum.deebot_n79"

    with pytest.raises(
        ServiceValidationError,
        match="not supported",
    ):
        await hass.services.async_call(
            DOMAIN,
            "raw_get_positions",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
            return_response=True,
        )
