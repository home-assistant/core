"""Tests for Roborock vacuums."""

from typing import Any
from unittest.mock import Mock, call

import pytest
from roborock import RoborockException
from roborock.roborock_typing import RoborockCommand
from syrupy.assertion import SnapshotAssertion
from vacuum_map_parser_base.map_data import Point

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.const import (
    GET_MAPS_SERVICE_NAME,
    GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
    SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
)
from homeassistant.components.vacuum import (
    SERVICE_CLEAN_SPOT,
    SERVICE_LOCATE,
    SERVICE_PAUSE,
    SERVICE_RETURN_TO_BASE,
    SERVICE_SEND_COMMAND,
    SERVICE_SET_FAN_SPEED,
    SERVICE_START,
    SERVICE_STOP,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from .conftest import FakeDevice

from tests.common import MockConfigEntry

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    # Note: Currently the Image platform is required to make these tests pass since
    # some initialization of the coordinator happens as a side effect of loading
    # image platform. Fix that and remove IMAGE here.
    return [Platform.VACUUM]


async def test_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Tests devices are registered in the entity registry."""
    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry.unique_id == DEVICE_ID

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.model_id == "roborock.vacuum.a27"


@pytest.mark.parametrize(
    ("service", "command", "service_params", "called_params"),
    [
        (SERVICE_START, RoborockCommand.APP_START, None, None),
        (SERVICE_PAUSE, RoborockCommand.APP_PAUSE, None, None),
        (SERVICE_STOP, RoborockCommand.APP_STOP, None, None),
        (SERVICE_RETURN_TO_BASE, RoborockCommand.APP_CHARGE, None, None),
        (SERVICE_CLEAN_SPOT, RoborockCommand.APP_SPOT, None, None),
        (SERVICE_LOCATE, RoborockCommand.FIND_ME, None, None),
        (
            SERVICE_SET_FAN_SPEED,
            RoborockCommand.SET_CUSTOM_MODE,
            {"fan_speed": "quiet"},
            [101],
        ),
        (
            SERVICE_SEND_COMMAND,
            RoborockCommand.GET_LED_STATUS,
            {"command": "get_led_status"},
            None,
        ),
    ],
)
async def test_commands(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    service: str,
    command: str,
    service_params: dict[str, Any],
    called_params: list | None,
    vacuum_command: Mock,
) -> None:
    """Test sending commands to the vacuum."""

    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID, **(service_params or {})}
    await hass.services.async_call(
        Platform.VACUUM,
        service,
        data,
        blocking=True,
    )
    assert vacuum_command.send.call_count == 1
    assert vacuum_command.send.call_args == call(command, params=called_params)


@pytest.mark.parametrize(
    ("in_cleaning_int", "in_returning_int", "expected_command"),
    [
        (0, 1, RoborockCommand.APP_CHARGE),
        (0, 0, RoborockCommand.APP_START),
        (1, 0, RoborockCommand.APP_START),
        (2, 0, RoborockCommand.RESUME_ZONED_CLEAN),
        (3, 0, RoborockCommand.RESUME_SEGMENT_CLEAN),
        (4, 0, RoborockCommand.APP_RESUME_BUILD_MAP),
    ],
)
async def test_resume_cleaning(
    hass: HomeAssistant,
    mock_roborock_entry: MockConfigEntry,
    in_cleaning_int: int,
    in_returning_int: int,
    expected_command: RoborockCommand,
    fake_vacuum: FakeDevice,
    vacuum_command: Mock,
) -> None:
    """Test resuming clean on start button when a clean is paused."""
    fake_vacuum.v1_properties.status.in_cleaning = in_cleaning_int
    fake_vacuum.v1_properties.status.in_returning = in_returning_int
    await async_setup_component(hass, DOMAIN, {})
    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(
        Platform.VACUUM,
        SERVICE_START,
        data,
        blocking=True,
    )
    assert vacuum_command.send.call_count == 1
    assert vacuum_command.send.call_args[0][0] == expected_command


async def test_failed_user_command(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    vacuum_command: Mock,
) -> None:
    """Test that when a user sends an invalid command, we raise HomeAssistantError."""
    data = {ATTR_ENTITY_ID: ENTITY_ID, "command": "fake_command"}
    vacuum_command.send.side_effect = RoborockException()
    with (
        pytest.raises(HomeAssistantError, match="Error while calling fake_command"),
    ):
        await hass.services.async_call(
            Platform.VACUUM,
            SERVICE_SEND_COMMAND,
            data,
            blocking=True,
        )


async def test_get_maps(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the service for maps correctly outputs rooms with the right name."""
    response = await hass.services.async_call(
        DOMAIN,
        GET_MAPS_SERVICE_NAME,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == snapshot


async def test_goto(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    vacuum_command: Mock,
) -> None:
    """Test sending the vacuum to specific coordinates."""
    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID, "x": 25500, "y": 25500}
    await hass.services.async_call(
        DOMAIN,
        SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
        data,
        blocking=True,
    )
    assert vacuum_command.send.call_count == 1
    assert vacuum_command.send.call_args == (
        call(RoborockCommand.APP_GOTO_TARGET, params=[25500, 25500])
    )


async def test_get_current_position(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that the service for getting the current position outputs the correct coordinates."""
    fake_vacuum.v1_properties.map_content.map_data.vacuum_position = Point(x=123, y=456)

    response = await hass.services.async_call(
        DOMAIN,
        GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
        return_response=True,
    )
    assert response == {
        "vacuum.roborock_s7_maxv": {
            "x": 123,
            "y": 456,
        },
    }


async def test_get_current_position_no_map_data(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that the service for getting the current position handles no map data error."""
    fake_vacuum.v1_properties.map_content.map_data = None

    with (
        pytest.raises(
            HomeAssistantError, match="Something went wrong creating the map"
        ),
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
            return_response=True,
        )


async def test_get_current_position_no_robot_position(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that the service for getting the current position handles no robot position error."""
    fake_vacuum.v1_properties.map_content.map_data.vacuum_position = None

    with (
        pytest.raises(HomeAssistantError, match="Robot position not found"),
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
            return_response=True,
        )
