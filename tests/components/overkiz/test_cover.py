"""Tests for the Overkiz cover platform."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any, NamedTuple
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
from homeassistant.components.overkiz.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform


class FixtureDevice(NamedTuple):
    """Test device binding a fixture file to a device URL."""

    fixture: str
    device_url: str


AWNING = FixtureDevice(
    "setup/local_somfy_connexoon_europe.json", "io://1234-1234-1234/5928357"
)
LOW_SPEED = FixtureDevice(
    "setup/cloud_nexity_rail_din_europe.json", "io://1234-5678-1698/141613"
)
PERGOLA = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json", "io://1234-5678-3293/7614902"
)
RTS = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json", "rts://1234-1234-6362/16730022"
)
SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json", "io://1234-1234-6233/12184029"
)
GARAGE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json", "io://1234-1234-6233/1166863"
)
TILTED_WINDOW = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json", "io://1234-5678-9373/10202865"
)
# Device with ClosureState=108
DYNAMIC_EXTERIOR_VENETIAN_BLIND = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json", "io://1234-5678-6508/4877511"
)
# Device with ClosureState=124
POSITIONABLE_ROLLER_SHUTTER_UNO = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_2.json", "io://1234-5678-1516/3656107"
)
POSITIONABLE_DUAL_ROLLER_SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_sc_europe.json", "io://1234-5678-5010/12931361"
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


def get_state(hass: HomeAssistant, entity_id: str) -> State:
    """Return a state and fail clearly if it is missing."""
    assert (state := hass.states.get(entity_id))
    return state


def get_entity_id(entity_registry: er.EntityRegistry, unique_id: str) -> str:
    """Resolve the entity id from the stable Overkiz unique id."""
    assert (
        entity_id := entity_registry.async_get_entity_id(
            COVER_DOMAIN, DOMAIN, unique_id
        )
    )
    return entity_id


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
    ("device", "service", "command_name", "expected_state"),
    [
        (SHUTTER, SERVICE_OPEN_COVER, "open", CoverState.OPENING),
        # Awning reports CLOSED after deploy — known integration bug to fix in follow-up
        (AWNING, SERVICE_OPEN_COVER, "deploy", CoverState.CLOSED),
        (GARAGE, SERVICE_OPEN_COVER, "open", CoverState.OPENING),
        (SHUTTER, SERVICE_CLOSE_COVER, "close", CoverState.CLOSING),
        # Awning reports CLOSED after undeploy — known integration bug to fix in follow-up
        (AWNING, SERVICE_CLOSE_COVER, "undeploy", CoverState.CLOSED),
        (GARAGE, SERVICE_CLOSE_COVER, "close", CoverState.CLOSING),
        (SHUTTER, SERVICE_STOP_COVER, "stop", None),
        (AWNING, SERVICE_STOP_COVER, "stop", None),
        (GARAGE, SERVICE_STOP_COVER, "stop", None),
    ],
    ids=[
        "open-roller-shutter",
        "open-awning",
        "open-garage-door",
        "close-roller-shutter",
        "close-awning",
        "close-garage-door",
        "stop-roller-shutter",
        "stop-awning",
        "stop-garage-door",
    ],
)
async def test_cover_service_actions(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    service: str,
    command_name: str,
    expected_state: str | None,
) -> None:
    """Test open, close, and stop cover services."""
    await setup_overkiz_integration(fixture=device.fixture)

    entity_id = get_entity_id(entity_registry, device.device_url)
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()

    if expected_state is not None:
        assert get_state(hass, entity_id).state == expected_state
    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
    )


@pytest.mark.parametrize(
    (
        "device",
        "command_name",
        "unique_id",
        "parameters",
        "position",
    ),
    [
        (SHUTTER, "setClosure", SHUTTER.device_url, (75,), 25),
        (AWNING, "setDeployment", AWNING.device_url, (80,), 80),
        (
            LOW_SPEED,
            "setClosureAndLinearSpeed",
            f"{LOW_SPEED.device_url}_low_speed",
            (65, OverkizCommandParam.LOWSPEED),
            35,
        ),
    ],
    ids=["roller-shutter", "awning", "low-speed"],
)
async def test_cover_set_position(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    command_name: str,
    unique_id: str,
    parameters: tuple[Any, ...],
    position: int,
) -> None:
    """Test cover position services and mapping."""
    await setup_overkiz_integration(fixture=device.fixture)

    entity_id = get_entity_id(entity_registry, unique_id)
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
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tilt services for a pergola from a full user setup."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    entity_id = get_entity_id(entity_registry, PERGOLA.device_url)
    state = get_state(hass, entity_id)

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
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert get_state(hass, entity_id).state == CoverState.OPENING
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
    assert get_state(hass, entity_id).state == CoverState.CLOSED

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert get_state(hass, entity_id).state == CoverState.CLOSING
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="closeSlats",
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
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
        {ATTR_ENTITY_ID: entity_id, ATTR_TILT_POSITION: 40},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=PERGOLA.device_url,
        command_name="setOrientation",
        parameters=(60,),
    )


async def test_cover_state_updates(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover state updates via events and execution tracking."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entity_id = get_entity_id(entity_registry, SHUTTER.device_url)
    assert get_state(hass, entity_id).attributes[ATTR_CURRENT_POSITION] == 0

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

    state = get_state(hass, entity_id)
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

    state = get_state(hass, entity_id)
    assert state.attributes[ATTR_CURRENT_POSITION] == 0
    assert state.state == CoverState.CLOSED

    # Execution tracking: state stays OPENING until execution completes
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert get_state(hass, entity_id).state == CoverState.OPENING

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
    assert get_state(hass, entity_id).state == CoverState.OPENING

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
    assert get_state(hass, entity_id).state == CoverState.OPEN

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
    assert get_state(hass, entity_id).state == STATE_UNAVAILABLE


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
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving direction detection for vertical covers based on current vs target position."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entity_id = get_entity_id(entity_registry, SHUTTER.device_url)
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

    assert get_state(hass, entity_id).state == expected_state


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
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving direction detection for awnings based on current vs target position."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    entity_id = get_entity_id(entity_registry, AWNING.device_url)
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

    assert get_state(hass, entity_id).state == expected_state


async def test_awning_direct_position_mapping(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test awning deployment uses direct mapping while vertical covers invert."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    entity_id = get_entity_id(entity_registry, AWNING.device_url)
    assert get_state(hass, entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: 35},
        blocking=True,
    )
    assert_command_call(
        mock_client,
        device_url=AWNING.device_url,
        command_name="setDeployment",
        parameters=(35,),
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
    assert get_state(hass, entity_id).attributes[ATTR_CURRENT_POSITION] == 100
