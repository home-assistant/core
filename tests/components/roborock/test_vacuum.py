"""Tests for Roborock vacuums."""

from typing import Any
from unittest.mock import AsyncMock, Mock, call, patch

import pytest
from roborock import RoborockCategory, RoborockException
from roborock.data import HomeDataDevice, HomeDataProduct
from roborock.data.b01_q10 import B01_Q10_DP
from roborock.data.b01_q10.b01_q10_code_mappings import YXDeviceState
from roborock.roborock_typing import RoborockCommand
from syrupy.assertion import SnapshotAssertion
from vacuum_map_parser_base.map_data import Point

from homeassistant.components.roborock import DOMAIN
from homeassistant.components.roborock.coordinator import (
    RoborockB01Q10UpdateCoordinator,
)
from homeassistant.components.roborock.services import (
    GET_MAPS_SERVICE_NAME,
    GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
    SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
)
from homeassistant.components.roborock.vacuum import _get_q10_status, _get_q10_wind_name
from homeassistant.components.vacuum import (
    DOMAIN as VACUUM_DOMAIN,
    SERVICE_CLEAN_AREA,
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
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component

from .conftest import FakeDevice, create_b01_q10_trait, set_trait_attributes
from .mock_data import BASE_URL, Q10_HOME_DATA_DEVICE, ROBOROCK_RRUID, STATUS, USER_DATA

from tests.common import MockConfigEntry
from tests.typing import WebSocketGenerator

ENTITY_ID = "vacuum.roborock_s7_maxv"
DEVICE_ID = "abc123"
Q7_ENTITY_ID = "vacuum.roborock_q7"
Q7_DEVICE_ID = "q7_duid"


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
        VACUUM_DOMAIN,
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

    async def refresh_properties() -> None:
        set_trait_attributes(fake_vacuum.v1_properties.status, STATUS)
        fake_vacuum.v1_properties.status.in_cleaning = in_cleaning_int
        fake_vacuum.v1_properties.status.in_returning = in_returning_int

    fake_vacuum.v1_properties.status.refresh.side_effect = refresh_properties

    await async_setup_component(hass, DOMAIN, {})
    vacuum = hass.states.get(ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: ENTITY_ID}
    await hass.services.async_call(
        VACUUM_DOMAIN,
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
            VACUUM_DOMAIN,
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


async def test_get_segments(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that async_get_segments returns segments from both maps."""
    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {
        "segments": [
            {"id": "0:16", "name": "Example room 1", "group": "Upstairs"},
            {"id": "0:17", "name": "Example room 2", "group": "Upstairs"},
            {"id": "0:18", "name": "Example room 3", "group": "Upstairs"},
            {"id": "1:16", "name": "Example room 1", "group": "Downstairs"},
            {"id": "1:17", "name": "Example room 2", "group": "Downstairs"},
            {"id": "1:18", "name": "Example room 3", "group": "Downstairs"},
        ]
    }


async def test_get_segments_no_map(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test that async_get_segments returns empty list when no map data."""
    fake_vacuum.v1_properties.home.home_map_info = {}

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": ENTITY_ID}
    )
    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"] == {"segments": []}


async def test_clean_segments(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_vacuum: FakeDevice,
    vacuum_command: Mock,
) -> None:
    """Test that clean_area service sends the correct segment clean command."""
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["1:16", "1:17"]},
            "last_seen_segments": [
                {"id": "0:16", "name": "Example room 1", "group": "Upstairs"},
                {"id": "0:17", "name": "Example room 2", "group": "Upstairs"},
                {"id": "0:18", "name": "Example room 3", "group": "Upstairs"},
                {"id": "1:16", "name": "Example room 1", "group": "Downstairs"},
                {"id": "1:17", "name": "Example room 2", "group": "Downstairs"},
                {"id": "1:18", "name": "Example room 3", "group": "Downstairs"},
            ],
        },
    )

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_CLEAN_AREA,
        {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
        blocking=True,
    )

    assert fake_vacuum.v1_properties.maps.set_current_map.call_count == 0
    assert vacuum_command.send.call_count == 1
    assert vacuum_command.send.call_args == call(
        RoborockCommand.APP_SEGMENT_CLEAN,
        params=[{"segments": [16, 17]}],
    )


async def test_clean_segments_different_map(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_vacuum: FakeDevice,
    vacuum_command: Mock,
) -> None:
    """Test that clean_area service switches maps when needed."""
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            "area_mapping": {
                "area_1": ["0:16", "0:17"],
                "area_2": ["0:18"],
                "area_3": ["1:16"],
            },
            "last_seen_segments": [
                {"id": "0:16", "name": "Example room 1", "group": "Upstairs"},
                {"id": "0:17", "name": "Example room 2", "group": "Upstairs"},
                {"id": "0:18", "name": "Example room 3", "group": "Upstairs"},
                {"id": "1:16", "name": "Example room 1", "group": "Downstairs"},
                {"id": "1:17", "name": "Example room 2", "group": "Downstairs"},
                {"id": "1:18", "name": "Example room 3", "group": "Downstairs"},
            ],
        },
    )

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_CLEAN_AREA,
        {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
        blocking=True,
    )

    assert fake_vacuum.v1_properties.maps.set_current_map.call_count == 1
    assert fake_vacuum.v1_properties.maps.set_current_map.call_args == call(0)
    assert vacuum_command.send.call_count == 1
    assert vacuum_command.send.call_args == call(
        RoborockCommand.APP_SEGMENT_CLEAN,
        params=[{"segments": [16, 17]}],
    )


async def test_clean_segments_multiple_maps_error(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that clean_area service raises error when segments from multiple maps."""
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["0:16", "1:17"]},
            "last_seen_segments": [
                {"id": "0:16", "name": "Example room 1", "group": "Upstairs"},
                {"id": "0:17", "name": "Example room 2", "group": "Upstairs"},
                {"id": "0:18", "name": "Example room 3", "group": "Upstairs"},
                {"id": "1:16", "name": "Example room 1", "group": "Downstairs"},
                {"id": "1:17", "name": "Example room 2", "group": "Downstairs"},
                {"id": "1:18", "name": "Example room 3", "group": "Downstairs"},
            ],
        },
    )

    with pytest.raises(
        ServiceValidationError,
        match="All segments must belong to the same map",
    ):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_CLEAN_AREA,
            {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
            blocking=True,
        )


async def test_clean_segments_malformed_id_wrong_parts(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that clean_area raises ServiceValidationError for a segment ID missing the colon separator."""
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["16"]},
            "last_seen_segments": [],
        },
    )

    with pytest.raises(
        ServiceValidationError,
        match="Invalid segment ID format: 16",
    ):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_CLEAN_AREA,
            {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
            blocking=True,
        )


async def test_clean_segments_malformed_id_non_integer(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that clean_area raises ServiceValidationError for a segment ID with non-integer parts."""
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["abc:16"]},
            "last_seen_segments": [],
        },
    )

    with pytest.raises(
        ServiceValidationError,
        match="Invalid segment ID format: abc:16",
    ):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_CLEAN_AREA,
            {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
            blocking=True,
        )


async def test_clean_segments_map_switch_fails(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test that clean_area raises ServiceValidationError when switching to the target map fails."""
    fake_vacuum.v1_properties.maps.set_current_map.side_effect = RoborockException()
    entity_registry.async_update_entity_options(
        ENTITY_ID,
        VACUUM_DOMAIN,
        {
            # Map flag 0 (Upstairs) differs from current map flag 1 (Downstairs),
            # so a map switch will be attempted and will fail.
            "area_mapping": {"area_1": ["0:16"]},
            "last_seen_segments": [],
        },
    )

    with pytest.raises(
        ServiceValidationError,
        match="Error while calling load_multi_map",
    ):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            SERVICE_CLEAN_AREA,
            {ATTR_ENTITY_ID: ENTITY_ID, "cleaning_area_id": ["area_1"]},
            blocking=True,
        )


# Tests for RoborockQ7Vacuum


@pytest.fixture
def fake_q7_vacuum(fake_devices: list[FakeDevice]) -> FakeDevice:
    """Get the fake Q7 vacuum device."""
    # The Q7 is the fourth device in the list (index 3) based on HOME_DATA
    return fake_devices[3]


@pytest.fixture(name="q7_vacuum_api", autouse=False)
def fake_q7_vacuum_api_fixture(
    fake_q7_vacuum: FakeDevice,
    send_message_exception: Exception | None,
) -> Mock:
    """Get the fake Q7 vacuum device API for asserting that commands happened."""
    assert fake_q7_vacuum.b01_q7_properties is not None
    api = fake_q7_vacuum.b01_q7_properties
    if send_message_exception is not None:
        # For exception tests, override side effects to raise the exception
        api.start_clean.side_effect = send_message_exception
        api.pause_clean.side_effect = send_message_exception
        api.stop_clean.side_effect = send_message_exception
        api.return_to_dock.side_effect = send_message_exception
        api.find_me.side_effect = send_message_exception
        api.set_fan_speed.side_effect = send_message_exception
        api.send.side_effect = send_message_exception
    return api


async def test_q7_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    setup_entry: MockConfigEntry,
) -> None:
    """Tests Q7 devices are registered in the entity registry."""
    entity_entry = entity_registry.async_get(Q7_ENTITY_ID)
    assert entity_entry.unique_id == Q7_DEVICE_ID

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None


@pytest.mark.parametrize(
    ("service", "api_method", "service_params", "expected_activity"),
    [
        (SERVICE_START, "start_clean", None, "cleaning"),
        (SERVICE_PAUSE, "pause_clean", None, "paused"),
        (SERVICE_STOP, "stop_clean", None, "idle"),
        (SERVICE_RETURN_TO_BASE, "return_to_dock", None, "returning"),
    ],
)
async def test_q7_state_changing_commands(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    service: str,
    api_method: str,
    service_params: dict[str, Any] | None,
    expected_activity: str,
    q7_vacuum_api: Mock,
    fake_q7_vacuum: FakeDevice,
) -> None:
    """Test sending state-changing commands to the Q7 vacuum."""
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: Q7_ENTITY_ID, **(service_params or {})}
    await hass.services.async_call(
        VACUUM_DOMAIN,
        service,
        data,
        blocking=True,
    )
    api_call = getattr(q7_vacuum_api, api_method)
    assert api_call.call_count == 1
    assert api_call.call_args[0] == ()

    # Verify the entity state was updated
    assert fake_q7_vacuum.b01_q7_properties is not None
    # Force coordinator refresh to get updated state
    coordinator = setup_entry.runtime_data.b01_q7[0]

    await coordinator.async_refresh()
    await hass.async_block_till_done()
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum
    assert vacuum.state == expected_activity


async def test_q7_locate_command(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_vacuum_api: Mock,
) -> None:
    """Test sending locate command to the Q7 vacuum."""
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_LOCATE,
        {ATTR_ENTITY_ID: Q7_ENTITY_ID},
        blocking=True,
    )
    assert q7_vacuum_api.find_me.call_count == 1
    assert q7_vacuum_api.find_me.call_args[0] == ()


async def test_q7_set_fan_speed_command(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_vacuum_api: Mock,
) -> None:
    """Test sending set_fan_speed command to the Q7 vacuum."""
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: Q7_ENTITY_ID, "fan_speed": "quiet"},
        blocking=True,
    )
    assert q7_vacuum_api.set_fan_speed.call_count == 1
    # set_fan_speed is called with the fan speed value as first argument
    assert len(q7_vacuum_api.set_fan_speed.call_args[0]) == 1


async def test_q7_send_command(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    q7_vacuum_api: Mock,
) -> None:
    """Test sending custom command to the Q7 vacuum."""
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum

    await hass.services.async_call(
        VACUUM_DOMAIN,
        SERVICE_SEND_COMMAND,
        {ATTR_ENTITY_ID: Q7_ENTITY_ID, "command": "test_command"},
        blocking=True,
    )
    assert q7_vacuum_api.send.call_count == 1
    # send is called with command as first argument and params as second
    assert q7_vacuum_api.send.call_args[0] == ("test_command", None)


async def test_q7_map_services_not_supported(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
) -> None:
    """Test map-related services are not supported for Q7."""
    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_MAPS_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q7_ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q7_ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q7_ENTITY_ID, "x": 1, "y": 2},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("service", "api_method", "service_params"),
    [
        (SERVICE_START, "start_clean", None),
        (SERVICE_PAUSE, "pause_clean", None),
        (SERVICE_STOP, "stop_clean", None),
        (SERVICE_RETURN_TO_BASE, "return_to_dock", None),
        (SERVICE_LOCATE, "find_me", None),
        (SERVICE_SET_FAN_SPEED, "set_fan_speed", {"fan_speed": "quiet"}),
        (SERVICE_SEND_COMMAND, "send", {"command": "test_command"}),
    ],
)
@pytest.mark.parametrize("send_message_exception", [RoborockException()])
async def test_q7_failed_commands(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    service: str,
    api_method: str,
    service_params: dict[str, Any] | None,
    q7_vacuum_api: Mock,
) -> None:
    """Test that when Q7 commands fail, we raise HomeAssistantError."""
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum
    # Store the original state to verify it doesn't change on error
    original_state = vacuum.state

    data = {ATTR_ENTITY_ID: Q7_ENTITY_ID, **(service_params or {})}
    command_name = (
        service_params.get("command", api_method) if service_params else api_method
    )

    with pytest.raises(HomeAssistantError, match=f"Error while calling {command_name}"):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            service,
            data,
            blocking=True,
        )

    # Verify the entity state remains unchanged after failed command
    await hass.async_block_till_done()
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum
    assert vacuum.state == original_state


async def test_q7_activity_none_status(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q7_vacuum: FakeDevice,
) -> None:
    """Test that activity returns None when status is None."""
    assert fake_q7_vacuum.b01_q7_properties is not None
    # Set status to None
    fake_q7_vacuum.b01_q7_properties._props_data.status = None

    # Force coordinator refresh to get updated state
    coordinator = setup_entry.runtime_data.b01_q7[0]
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    # Verify the entity state is unknown when status is None
    vacuum = hass.states.get(Q7_ENTITY_ID)
    assert vacuum
    assert vacuum.state == "unknown"


async def test_q7_coordinator_refresh_error_is_update_failed(
    setup_entry: MockConfigEntry,
    fake_q7_vacuum: FakeDevice,
) -> None:
    """Test Q7 coordinator wraps query errors as UpdateFailed."""
    assert fake_q7_vacuum.b01_q7_properties is not None

    coordinator = setup_entry.runtime_data.b01_q7[0]
    fake_q7_vacuum.b01_q7_properties.query_values.side_effect = RoborockException(
        "boom"
    )

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


async def test_q7_coordinator_none_data_is_update_failed(
    setup_entry: MockConfigEntry,
    fake_q7_vacuum: FakeDevice,
) -> None:
    """Test Q7 coordinator raises UpdateFailed when query returns no data."""
    assert fake_q7_vacuum.b01_q7_properties is not None

    coordinator = setup_entry.runtime_data.b01_q7[0]
    fake_q7_vacuum.b01_q7_properties._props_data = None

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


# Tests for RoborockQ10Vacuum

Q10_ENTITY_ID = "vacuum.roborock_q10_s5"
Q10_DEVICE_ID = "q10_s5_plus_duid"


@pytest.fixture
def q10_platforms() -> list[Platform]:
    """Fixture to set platforms used in Q10 tests."""
    return [Platform.VACUUM]


@pytest.fixture(name="q10_fake_device")
def q10_fake_device_fixture() -> FakeDevice:
    """Create a fake Q10 S5+ device for testing."""
    device_data = HomeDataDevice.from_dict(Q10_HOME_DATA_DEVICE)
    product_data = HomeDataProduct(
        id="q10_product_id",
        name="Roborock Q10 S5+",
        code="ss07",
        model="roborock.vacuum.ss07",
        category=RoborockCategory.VACUUM,
    )

    fake_device = FakeDevice(
        device_info=device_data,
        product=product_data,
    )
    fake_device.is_connected = True
    fake_device.is_local_connected = True
    fake_device.b01_q10_properties = create_b01_q10_trait()

    return fake_device


@pytest.fixture(name="q10_device_manager")
def q10_device_manager_fixture(q10_fake_device: FakeDevice) -> AsyncMock:
    """Fixture to create a fake device manager with Q10 device."""
    device_manager = AsyncMock()
    device_manager.get_devices = AsyncMock(return_value=[q10_fake_device])
    return device_manager


@pytest.fixture(name="q10_config_entry")
def q10_config_entry_fixture(hass: HomeAssistant) -> MockConfigEntry:
    """Create a Q10 config entry."""
    config_entry = MockConfigEntry(
        domain="roborock",
        title="user@domain.com",
        data={
            "username": "user@domain.com",
            "user_data": USER_DATA.as_dict(),
            "base_url": BASE_URL,
        },
        unique_id=ROBOROCK_RRUID,
        version=1,
        minor_version=2,
    )
    config_entry.add_to_hass(hass)
    return config_entry


async def test_q10_registry_entries(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Tests Q10 devices are registered in the entity registry."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_entry = entity_registry.async_get(Q10_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.unique_id == Q10_DEVICE_ID

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry is not None
    assert device_entry.model == "roborock.vacuum.ss07"


async def test_q10_unload_closes_subscription(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
) -> None:
    """Test unloading Q10 closes the subscription loop."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    assert q10_config_entry.state is not None

    # Ensure the coordinator has started the Q10 subscription loop first.
    await hass.services.async_call(
        Platform.VACUUM,
        SERVICE_START,
        {ATTR_ENTITY_ID: Q10_ENTITY_ID},
        blocking=True,
    )

    assert await hass.config_entries.async_unload(q10_config_entry.entry_id)
    await hass.async_block_till_done()

    assert q10_fake_device.b01_q10_properties.close.call_count == 1


@pytest.mark.parametrize(
    ("service", "api_method", "service_params", "expected_activity"),
    [
        (SERVICE_START, "start_clean", None, "cleaning"),
        (SERVICE_PAUSE, "pause_clean", None, "paused"),
        (SERVICE_STOP, "stop_clean", None, "idle"),
        (SERVICE_RETURN_TO_BASE, "return_to_dock", None, "returning"),
    ],
)
async def test_q10_state_changing_commands(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
    service: str,
    api_method: str,
    service_params: dict[str, Any] | None,
    expected_activity: str,
) -> None:
    """Test sending state-changing commands to the Q10 vacuum."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum

    data = {ATTR_ENTITY_ID: Q10_ENTITY_ID, **(service_params or {})}
    await hass.services.async_call(
        Platform.VACUUM,
        service,
        data,
        blocking=True,
    )

    api = q10_fake_device.b01_q10_properties
    if service == SERVICE_START:
        assert api.vacuum.start_clean.call_count == 1
        assert api.vacuum.start_clean.call_args[0] == ()
    else:
        api_call = getattr(api.vacuum, api_method)
        assert api_call.call_count == 1
        assert api_call.call_args[0] == ()

    # Force coordinator refresh to get updated state
    await hass.async_block_till_done()
    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum
    assert vacuum.state == expected_activity


async def test_q10_locate_command_not_supported(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test that locate command is not supported for Q10 vacuum."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum

    with pytest.raises(
        HomeAssistantError,
        match="does not support action vacuum\\.locate",
    ):
        await hass.services.async_call(
            Platform.VACUUM,
            SERVICE_LOCATE,
            {ATTR_ENTITY_ID: Q10_ENTITY_ID},
            blocking=True,
        )


async def test_q10_state_unknown_status_maps_to_unknown(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
) -> None:
    """Test that UNKNOWN Q10 status maps to Home Assistant unknown state."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    q10_fake_device.b01_q10_properties.status.update_from_dps(
        {B01_Q10_DP.STATUS: YXDeviceState.UNKNOWN.code}
    )
    await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum
    assert vacuum.state == "unknown"


async def test_q10_set_fan_speed_command(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
) -> None:
    """Test sending set_fan_speed command to the Q10 vacuum."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum

    await hass.services.async_call(
        Platform.VACUUM,
        SERVICE_SET_FAN_SPEED,
        {ATTR_ENTITY_ID: Q10_ENTITY_ID, "fan_speed": "quiet"},
        blocking=True,
    )

    # Q10 uses command.send with B01_Q10_DP.FAN_LEVEL
    api = q10_fake_device.b01_q10_properties
    assert api.command.send.call_count == 1


async def test_q10_fan_speed_labels_are_capitalized(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test Q10 fan speed labels are exposed with leading capitals."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum
    assert vacuum.attributes["fan_speed"] == "Normal"
    assert vacuum.attributes["fan_speed_list"] == [
        "Quiet",
        "Normal",
        "Strong",
        "Max",
        "Super",
    ]


async def test_q10_clean_spot_command(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
) -> None:
    """Test sending clean_spot command to the Q10 vacuum."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum

    await hass.services.async_call(
        Platform.VACUUM,
        SERVICE_CLEAN_SPOT,
        {ATTR_ENTITY_ID: Q10_ENTITY_ID},
        blocking=True,
    )

    # Q10 starts cleaning using vacuum.start_clean
    api = q10_fake_device.b01_q10_properties
    assert api.vacuum.start_clean.call_count == 1


async def test_q10_start_uses_resume_when_paused(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
) -> None:
    """Test Q10 start sends resume command when vacuum is paused."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    q10_fake_device.b01_q10_properties.status.data[B01_Q10_DP.STATUS] = (
        YXDeviceState.PAUSE_STATE.code
    )

    await hass.services.async_call(
        Platform.VACUUM,
        SERVICE_START,
        {ATTR_ENTITY_ID: Q10_ENTITY_ID},
        blocking=True,
    )

    api = q10_fake_device.b01_q10_properties
    assert api.command.send.call_count == 1
    assert api.command.send.call_args.kwargs == {
        "command": B01_Q10_DP.RESUME,
        "params": {},
    }


async def test_q10_send_command_not_supported(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test that send_command is not supported for Q10 vacuum."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum

    with pytest.raises(
        HomeAssistantError,
        match="does not support action vacuum\\.send_command",
    ):
        await hass.services.async_call(
            Platform.VACUUM,
            SERVICE_SEND_COMMAND,
            {ATTR_ENTITY_ID: Q10_ENTITY_ID, "command": "test_command"},
            blocking=True,
        )


async def test_q10_map_services_not_supported(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test map-related services are not supported for Q10."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_MAPS_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q10_ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            GET_VACUUM_CURRENT_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q10_ENTITY_ID},
            blocking=True,
            return_response=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="This command is not supported for this device model",
    ):
        await hass.services.async_call(
            DOMAIN,
            SET_VACUUM_GOTO_POSITION_SERVICE_NAME,
            {ATTR_ENTITY_ID: Q10_ENTITY_ID, "x": 1, "y": 2},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("raw_data", "expected_status", "expected_fan"),
    [
        ({}, None, None),
        (
            {B01_Q10_DP.STATUS: -1, B01_Q10_DP.FAN_LEVEL: -1},
            YXDeviceState.UNKNOWN,
            "Unknown",
        ),
    ],
)
def test_q10_helper_mappings(
    raw_data: dict[Any, Any],
    expected_status: YXDeviceState | None,
    expected_fan: str | None,
) -> None:
    """Test Q10 helper mappings for unknown and missing values."""
    assert _get_q10_status(raw_data) is expected_status
    assert _get_q10_wind_name(raw_data) == expected_fan


async def test_q10_coordinator_refresh_returns_trait_status_data(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test Q10 coordinator returns normalized data from status trait."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: RoborockB01Q10UpdateCoordinator = (
        q10_config_entry.runtime_data.b01_q10[0]
    )
    coordinator.api.refresh = AsyncMock()
    coordinator.api.status.data = {B01_Q10_DP.STATUS: YXDeviceState.PAUSE_STATE.code}

    result = await coordinator._async_update_data()

    # The coordinator now returns the status object directly
    assert result is coordinator.api.status
    # Optionally, check the .data attribute
    assert result.data == {B01_Q10_DP.STATUS: YXDeviceState.PAUSE_STATE.code}


async def test_q10_coordinator_refresh_with_empty_status_returns_empty(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test Q10 coordinator returns empty data when status trait has no values."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: RoborockB01Q10UpdateCoordinator = (
        q10_config_entry.runtime_data.b01_q10[0]
    )
    coordinator.api.refresh = AsyncMock()
    coordinator.api.status.data = {}

    result = await coordinator._async_update_data()

    assert result is coordinator.api.status
    assert result.data == {}


async def test_q10_coordinator_refresh_error_is_update_failed(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
) -> None:
    """Test Q10 coordinator wraps refresh errors as UpdateFailed."""
    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    coordinator: RoborockB01Q10UpdateCoordinator = (
        q10_config_entry.runtime_data.b01_q10[0]
    )
    coordinator.api.refresh.side_effect = RoborockException("boom")

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()


@pytest.mark.parametrize(
    ("service", "api_method", "service_params"),
    [
        (SERVICE_START, "start_clean", None),
        (SERVICE_PAUSE, "pause_clean", None),
        (SERVICE_STOP, "stop_clean", None),
        (SERVICE_RETURN_TO_BASE, "return_to_dock", None),
    ],
)
@pytest.mark.parametrize("send_message_exception", [RoborockException()])
async def test_q10_failed_commands(
    hass: HomeAssistant,
    q10_config_entry: MockConfigEntry,
    q10_device_manager: AsyncMock,
    q10_platforms: list[Platform],
    q10_fake_device: FakeDevice,
    service: str,
    api_method: str,
    service_params: dict[str, Any] | None,
    send_message_exception: Exception,
) -> None:
    """Test that when Q10 commands fail, we raise HomeAssistantError."""
    # Configure the API to raise exceptions
    api = q10_fake_device.b01_q10_properties
    api.vacuum.start_clean.side_effect = send_message_exception
    api.vacuum.pause_clean.side_effect = send_message_exception
    api.vacuum.stop_clean.side_effect = send_message_exception
    api.vacuum.return_to_dock.side_effect = send_message_exception

    with (
        patch("homeassistant.components.roborock.PLATFORMS", q10_platforms),
        patch(
            "homeassistant.components.roborock.create_device_manager",
            return_value=q10_device_manager,
        ),
    ):
        await hass.config_entries.async_setup(q10_config_entry.entry_id)
        await hass.async_block_till_done()

    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum
    original_state = vacuum.state

    data = {ATTR_ENTITY_ID: Q10_ENTITY_ID, **(service_params or {})}

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            Platform.VACUUM,
            service,
            data,
            blocking=True,
        )

    # Verify the entity state remains unchanged after failed command
    await hass.async_block_till_done()
    vacuum = hass.states.get(Q10_ENTITY_ID)
    assert vacuum
    assert vacuum.state == original_state
