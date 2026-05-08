"""Tests for the Overkiz cover platform."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import EventName, ExecutionState, OverkizCommandParam, OverkizState
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_CURRENT_TILT_POSITION,
    ATTR_POSITION,
    ATTR_TILT_POSITION,
    DOMAIN as COVER_DOMAIN,
    SERVICE_CLOSE_COVER,
    SERVICE_CLOSE_COVER_TILT,
    SERVICE_OPEN_COVER,
    SERVICE_OPEN_COVER_TILT,
    SERVICE_SET_COVER_POSITION,
    SERVICE_SET_COVER_TILT_POSITION,
    SERVICE_STOP_COVER,
    SERVICE_STOP_COVER_TILT,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform

AWNING = FixtureDevice(
    "setup/local_somfy_connexoon_europe.json",
    "io://1234-1234-1234/5928357",
    "cover.terrace_awning",
)
LOW_SPEED = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json",
    "io://1234-5678-1698/141613",
    "cover.nursery_shutter",
)
PERGOLA = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "io://1234-5678-3293/7614902",
    "cover.garden_pergola",
)
UP_DOWN_BIOCLIMATIC_PERGOLA = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "rts://1234-5678-3293/16757826",
    "cover.kitchen_pergola",
)
RTS = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16730022",
    "cover.patio_shutter",
)
SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/12184029",
    "cover.garden_house_shutter",
)
GARAGE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/1166863",
    "cover.main_garage_door",
)
TILTED_WINDOW = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json",
    "io://1234-5678-9373/10202865",
    "cover.bedroom_blinds",
)
# Device with ClosureState=108
DYNAMIC_EXTERIOR_VENETIAN_BLIND = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/4877511",
    "cover.dining_room_blinds",
)
# Device with ClosureState=124
POSITIONABLE_ROLLER_SHUTTER_UNO = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_2.json",
    "io://1234-5678-1516/3656107",
    "cover.hallway_shutter",
)
POSITIONABLE_DUAL_ROLLER_SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_sc_europe.json",
    "io://1234-5678-5010/12931361",
    "cover.basement_roller_shutter",
)
TILT_ONLY_VENETIAN_BLIND = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16730044",
    "cover.jaloezie",
)
DYNAMIC_GARAGE_DOOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16730050",
    "cover.garage_door",
)
DYNAMIC_GARAGE_DOOR_OGP = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/6632544",
    "cover.ogp_garage_door",
)
PARTIAL_GARAGE_DOOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/7433515",
    "cover.partial_garage_door",
)

SNAPSHOT_FIXTURES = [
    AWNING,
    LOW_SPEED,
    PERGOLA,
    RTS,
    SHUTTER,
    TILTED_WINDOW,
    DYNAMIC_EXTERIOR_VENETIAN_BLIND,
    POSITIONABLE_ROLLER_SHUTTER_UNO,
    POSITIONABLE_DUAL_ROLLER_SHUTTER,
]


@pytest.fixture(autouse=True)
def fixture_platforms() -> Generator[None]:
    """Limit platforms to cover only."""
    with patch("homeassistant.components.overkiz.PLATFORMS", [Platform.COVER]):
        yield


@pytest.mark.parametrize(
    "device",
    SNAPSHOT_FIXTURES,
    ids=[Path(device.fixture).name for device in SNAPSHOT_FIXTURES],
)
async def test_cover_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    device: FixtureDevice,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=device.fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    ("device", "service", "command_name", "parameters", "expected_state"),
    [
        (SHUTTER, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (AWNING, SERVICE_OPEN_COVER, "deploy", None, CoverState.OPENING),
        (GARAGE, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_GARAGE_DOOR, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_GARAGE_DOOR_OGP, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (PARTIAL_GARAGE_DOOR, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_OPEN_COVER,
            "open",
            [0],
            CoverState.OPENING,
        ),
        (TILT_ONLY_VENETIAN_BLIND, SERVICE_OPEN_COVER, "open", [0], CoverState.OPENING),
        (SHUTTER, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (AWNING, SERVICE_CLOSE_COVER, "undeploy", None, CoverState.CLOSING),
        (GARAGE, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (DYNAMIC_GARAGE_DOOR, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (
            DYNAMIC_GARAGE_DOOR_OGP,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (PARTIAL_GARAGE_DOOR, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_CLOSE_COVER,
            "close",
            [0],
            CoverState.CLOSING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER,
            "close",
            [0],
            CoverState.CLOSING,
        ),
        (SHUTTER, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (AWNING, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (GARAGE, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_GARAGE_DOOR, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_GARAGE_DOOR_OGP, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (PARTIAL_GARAGE_DOOR, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_STOP_COVER,
            "stop",
            [0],
            STATE_UNKNOWN,
        ),
        (TILT_ONLY_VENETIAN_BLIND, SERVICE_STOP_COVER, "stop", [0], STATE_UNKNOWN),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_OPEN_COVER_TILT,
            "tiltPositive",
            [1, 0],
            CoverState.OPENING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER_TILT,
            "tiltNegative",
            [1, 0],
            CoverState.CLOSING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_STOP_COVER_TILT,
            "stop",
            [0],
            STATE_UNKNOWN,
        ),
    ],
    ids=[
        "open-roller-shutter",
        "open-awning",
        "open-garage-door",
        "open-dynamic-garage-door",
        "open-dynamic-garage-door-ogp",
        "open-partial-garage-door",
        "open-up-down-bioclimatic-pergola",
        "open-tilt-only-venetian-blind",
        "close-roller-shutter",
        "close-awning",
        "close-garage-door",
        "close-dynamic-garage-door",
        "close-dynamic-garage-door-ogp",
        "close-partial-garage-door",
        "close-up-down-bioclimatic-pergola",
        "close-tilt-only-venetian-blind",
        "stop-roller-shutter",
        "stop-awning",
        "stop-garage-door",
        "stop-dynamic-garage-door",
        "stop-dynamic-garage-door-ogp",
        "stop-partial-garage-door",
        "stop-up-down-bioclimatic-pergola",
        "stop-tilt-only-venetian-blind",
        "open-tilt-tilt-only-venetian-blind",
        "close-tilt-tilt-only-venetian-blind",
        "stop-tilt-tilt-only-venetian-blind",
    ],
)
async def test_cover_service_actions(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    service: str,
    command_name: str,
    parameters: list[Any] | None,
    expected_state: CoverState | str,
) -> None:
    """Test open, close, and stop cover and tilt services."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: device.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert hass.states.get(device.entity_id).state == expected_state

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


@pytest.mark.parametrize(
    (
        "device",
        "entity_id",
        "command_name",
        "parameters",
        "position",
    ),
    [
        (SHUTTER, SHUTTER.entity_id, "setClosure", [75], 25),
        (AWNING, AWNING.entity_id, "setDeployment", [80], 80),
        (
            LOW_SPEED,
            "cover.nursery_shutter_low_speed",
            "setClosureAndLinearSpeed",
            [65, OverkizCommandParam.LOWSPEED],
            35,
        ),
    ],
    ids=["roller-shutter", "awning", "low-speed"],
)
async def test_cover_set_position(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    entity_id: str,
    command_name: str,
    parameters: list[Any],
    position: int,
) -> None:
    """Test cover position services and mapping."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: position},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


async def test_cover_tilt_services(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tilt services for a pergola from a full user setup."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    state = hass.states.get(PERGOLA.entity_id)
    assert state
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes["supported_features"] == (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER_TILT,
        {ATTR_ENTITY_ID: PERGOLA.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(PERGOLA.entity_id).state == CoverState.OPENING
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="openSlats",
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=PERGOLA.device_url,
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED.value,
            )
        ],
    )
    assert hass.states.get(PERGOLA.entity_id).state == CoverState.CLOSED

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: PERGOLA.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(PERGOLA.entity_id).state == CoverState.CLOSING
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="closeSlats",
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: PERGOLA.entity_id},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="stop",
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: PERGOLA.entity_id, ATTR_TILT_POSITION: 40},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="setOrientation",
        parameters=[60],
    )


async def test_cover_state_updates(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover state updates via events and execution tracking."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    assert hass.states.get(SHUTTER.entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    # Position update via device state change event
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_CLOSURE.value,
                        "type": 1,
                        "value": 0,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_CLOSURE.value,
                        "type": 1,
                        "value": 0,
                    },
                    {
                        "name": OverkizState.CORE_MOVING.value,
                        "type": 6,
                        "value": False,
                    },
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED.value,
                        "type": 3,
                        "value": OverkizCommandParam.OPEN.value,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(SHUTTER.entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 100
    assert state.state == CoverState.OPEN

    # Position update to closed
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_CLOSURE.value,
                        "type": 1,
                        "value": 100,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_CLOSURE.value,
                        "type": 1,
                        "value": 100,
                    },
                    {
                        "name": OverkizState.CORE_MOVING.value,
                        "type": 6,
                        "value": False,
                    },
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED.value,
                        "type": 3,
                        "value": OverkizCommandParam.CLOSED.value,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(SHUTTER.entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    assert state.state == CoverState.CLOSED

    # Execution tracking: state stays OPENING until execution completes
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: SHUTTER.entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPENING

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_CLOSURE.value,
                        "type": 1,
                        "value": 0,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_CLOSURE.value,
                        "type": 1,
                        "value": 0,
                    },
                    {
                        "name": OverkizState.CORE_MOVING.value,
                        "type": 6,
                        "value": False,
                    },
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED.value,
                        "type": 3,
                        "value": OverkizCommandParam.OPEN.value,
                    },
                ],
            )
        ],
    )
    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPENING

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED.value,
            )
        ],
    )
    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPEN

    # Unavailability propagates to entity state
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_UNAVAILABLE.value, device_url=SHUTTER.device_url
            )
        ],
    )
    assert hass.states.get(SHUTTER.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("device_states", "expected_state"),
    [
        (
            [
                {"name": OverkizState.CORE_MOVING.value, "type": 6, "value": True},
                {"name": OverkizState.CORE_CLOSURE.value, "type": 1, "value": 75},
                {
                    "name": OverkizState.CORE_TARGET_CLOSURE.value,
                    "type": 1,
                    "value": 20,
                },
            ],
            CoverState.OPENING,
        ),
        (
            [
                {"name": OverkizState.CORE_MOVING.value, "type": 6, "value": True},
                {"name": OverkizState.CORE_CLOSURE.value, "type": 1, "value": 20},
                {
                    "name": OverkizState.CORE_TARGET_CLOSURE.value,
                    "type": 1,
                    "value": 75,
                },
            ],
            CoverState.CLOSING,
        ),
    ],
    ids=["opening", "closing"],
)
async def test_vertical_cover_moving_direction(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving direction detection for vertical covers based on current vs target position."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                device_states=device_states,
            )
        ],
    )

    assert hass.states.get(SHUTTER.entity_id).state == expected_state


@pytest.mark.parametrize(
    ("device_states", "expected_state"),
    [
        (
            [
                {"name": OverkizState.CORE_MOVING.value, "type": 6, "value": True},
                {
                    "name": OverkizState.CORE_DEPLOYMENT.value,
                    "type": 1,
                    "value": 20,
                },
                {
                    "name": OverkizState.CORE_TARGET_CLOSURE.value,
                    "type": 1,
                    "value": 80,
                },
            ],
            CoverState.OPENING,
        ),
        (
            [
                {"name": OverkizState.CORE_MOVING.value, "type": 6, "value": True},
                {
                    "name": OverkizState.CORE_DEPLOYMENT.value,
                    "type": 1,
                    "value": 80,
                },
                {
                    "name": OverkizState.CORE_TARGET_CLOSURE.value,
                    "type": 1,
                    "value": 20,
                },
            ],
            CoverState.CLOSING,
        ),
    ],
    ids=["opening", "closing"],
)
async def test_awning_moving_direction(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving direction detection for awnings based on current vs target position."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=AWNING.device_url,
                device_states=device_states,
            )
        ],
    )

    assert hass.states.get(AWNING.entity_id).state == expected_state


async def test_awning_direct_position_mapping(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test awning deployment uses direct mapping while vertical covers invert."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    assert hass.states.get(AWNING.entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: AWNING.entity_id, ATTR_POSITION: 35},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=AWNING.device_url,
        command_name="setDeployment",
        parameters=[35],
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=AWNING.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_DEPLOYMENT.value,
                        "type": 1,
                        "value": 100,
                    }
                ],
            )
        ],
    )
    assert hass.states.get(AWNING.entity_id).attributes[ATTR_CURRENT_POSITION] == 100


async def test_moving_offset_missing_closure_states(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that is_opening/is_closing return None when closure states are missing while moving."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=PERGOLA.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_MOVING.value,
                        "type": 6,
                        "value": True,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(PERGOLA.entity_id)
    assert state.state == CoverState.CLOSED


async def test_moving_offset_none_values(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that is_opening/is_closing return None when closure value_as_int is None."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_MOVING.value,
                        "type": 6,
                        "value": True,
                    },
                    {
                        "name": OverkizState.CORE_CLOSURE.value,
                        "type": 1,
                        "value": None,
                    },
                    {
                        "name": OverkizState.CORE_TARGET_CLOSURE.value,
                        "type": 1,
                        "value": 50,
                    },
                    {
                        "name": OverkizState.CORE_OPEN_CLOSED.value,
                        "type": 3,
                        "value": OverkizCommandParam.OPEN.value,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(SHUTTER.entity_id)
    assert state.state == CoverState.OPEN


async def test_tilt_position_none_value(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that tilt position returns None when value_as_int is None."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=PERGOLA.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_SLATE_ORIENTATION.value,
                        "type": 1,
                        "value": None,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(PERGOLA.entity_id)
    assert ATTR_CURRENT_TILT_POSITION not in state.attributes


async def test_low_speed_cover_open_close(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Test low speed cover open and close send correct commands."""
    await setup_overkiz_integration(fixture=LOW_SPEED.fixture)
    entity_id = "cover.nursery_shutter_low_speed"

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=LOW_SPEED.device_url,
        command_name="setClosureAndLinearSpeed",
        parameters=[0, OverkizCommandParam.LOWSPEED],
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=LOW_SPEED.device_url,
        command_name="setClosureAndLinearSpeed",
        parameters=[100, OverkizCommandParam.LOWSPEED],
    )
