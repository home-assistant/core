"""Tests for the Overkiz cover platform."""

from __future__ import annotations

from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import humps
from pyoverkiz.enums import EventName, ExecutionState, OverkizCommandParam, OverkizState
from pyoverkiz.models import Event
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
from homeassistant.components.overkiz.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MockOverkizClient

from tests.common import async_fire_time_changed, snapshot_platform

FIXTURE_AWNING = "setup/setup_local.json"
FIXTURE_LOW_SPEED = "setup/setup_nexity_2.json"
FIXTURE_PERGOLA = "setup/setup_local_tahoma.json"
FIXTURE_RTS = "setup/setup_hi_kumo.json"
FIXTURE_SHUTTERS_AND_GARAGE = "setup/setup_tahoma_3.json"
FIXTURE_TILTED_WINDOW = "setup/setup_local_with_climate.json"

AWNING_URL = "io://1234-1234-1234/5928357"
LOW_SPEED_URL = "io://1234-5678-1698/141613"
LOW_SPEED_OTHER_URL = "io://1234-5678-1698/4080031"
PERGOLA_URL = "io://1234-5678-3293/7614902"
RTS_URL = "rts://1234-1234-6362/16730022"
GARAGE_URL = "io://1234-1234-6233/1166863"
SHUTTER_URL = "io://1234-1234-6233/12184029"

SNAPSHOT_FIXTURES = [
    FIXTURE_AWNING,
    FIXTURE_LOW_SPEED,
    FIXTURE_PERGOLA,
    FIXTURE_RTS,
    FIXTURE_SHUTTERS_AND_GARAGE,
    FIXTURE_TILTED_WINDOW,
]


@dataclass(frozen=True, slots=True)
class CoverCommandCase:
    """Describe a service call against one device in a real setup fixture."""

    fixture: str
    device_url: str
    command_name: str
    expected_state: str | None = None
    entity_unique_id: str | None = None
    parameters: tuple[Any, ...] = ()


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


def assert_command_call(
    mock_client: MockOverkizClient,
    *,
    device_url: str,
    command_name: str,
    parameters: tuple[Any, ...] = (),
) -> None:
    """Assert the latest executed command."""
    assert mock_client.execute_command.await_count == 1
    args = mock_client.execute_command.await_args.args
    assert args[0] == device_url
    assert args[1].name == command_name
    assert args[1].parameters == list(parameters)
    assert args[2] == "Home Assistant"


def build_event(
    name: str,
    *,
    device_url: str,
    device_states: list[dict[str, Any]] | None = None,
    exec_id: str | None = None,
    new_state: str | None = None,
) -> Event:
    """Create an Overkiz event from a small JSON payload."""
    payload: dict[str, Any] = {"name": name, "deviceURL": device_url}
    if device_states is not None:
        payload["deviceStates"] = device_states
    if exec_id is not None:
        payload["execId"] = exec_id
    if new_state is not None:
        payload["newState"] = new_state
    return Event(**humps.decamelize(payload))


async def async_deliver_events(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_client: MockOverkizClient,
    *event_batches: list[Event],
) -> None:
    """Queue event batches and advance time to trigger a coordinator refresh."""
    mock_client.queue_events(*event_batches)
    freezer.tick(UPDATE_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    "fixture",
    SNAPSHOT_FIXTURES,
    ids=[Path(fixture).name for fixture in SNAPSHOT_FIXTURES],
)
async def test_cover_entities_snapshot(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    fixture: str,
) -> None:
    """Test representative real setups via snapshot."""
    config_entry = await setup_overkiz_integration(fixture=fixture)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


@pytest.mark.parametrize(
    "case",
    [
        CoverCommandCase(
            FIXTURE_SHUTTERS_AND_GARAGE,
            SHUTTER_URL,
            "open",
            CoverState.OPENING,
        ),
        CoverCommandCase(FIXTURE_AWNING, AWNING_URL, "deploy", CoverState.CLOSED),
        CoverCommandCase(
            FIXTURE_SHUTTERS_AND_GARAGE,
            GARAGE_URL,
            "open",
            CoverState.OPENING,
        ),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_open(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    case: CoverCommandCase,
) -> None:
    """Test opening supported covers via the service layer."""
    await setup_overkiz_integration(fixture=case.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, case.entity_unique_id or case.device_url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert get_state(hass, entity_id).state == case.expected_state
    assert_command_call(
        mock_client,
        device_url=case.device_url,
        command_name=case.command_name,
    )


@pytest.mark.parametrize(
    "case",
    [
        CoverCommandCase(
            FIXTURE_SHUTTERS_AND_GARAGE,
            SHUTTER_URL,
            "close",
            CoverState.CLOSING,
        ),
        CoverCommandCase(FIXTURE_AWNING, AWNING_URL, "undeploy", CoverState.CLOSED),
        CoverCommandCase(
            FIXTURE_SHUTTERS_AND_GARAGE,
            GARAGE_URL,
            "close",
            CoverState.CLOSING,
        ),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_close(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    case: CoverCommandCase,
) -> None:
    """Test closing supported covers via the service layer."""
    await setup_overkiz_integration(fixture=case.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, case.entity_unique_id or case.device_url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert get_state(hass, entity_id).state == case.expected_state
    assert_command_call(
        mock_client,
        device_url=case.device_url,
        command_name=case.command_name,
    )


@pytest.mark.parametrize(
    "case",
    [
        CoverCommandCase(FIXTURE_SHUTTERS_AND_GARAGE, SHUTTER_URL, "stop"),
        CoverCommandCase(FIXTURE_AWNING, AWNING_URL, "stop"),
        CoverCommandCase(FIXTURE_SHUTTERS_AND_GARAGE, GARAGE_URL, "stop"),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_stop(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    case: CoverCommandCase,
) -> None:
    """Test stop commands for supported covers."""
    await setup_overkiz_integration(fixture=case.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, case.entity_unique_id or case.device_url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=case.device_url,
        command_name=case.command_name,
    )


@pytest.mark.parametrize(
    ("case", "position"),
    [
        (
            CoverCommandCase(
                FIXTURE_SHUTTERS_AND_GARAGE,
                SHUTTER_URL,
                "setClosure",
                parameters=(75,),
            ),
            25,
        ),
        (
            CoverCommandCase(
                FIXTURE_AWNING,
                AWNING_URL,
                "setDeployment",
                parameters=(80,),
            ),
            80,
        ),
        (
            CoverCommandCase(
                FIXTURE_LOW_SPEED,
                LOW_SPEED_URL,
                "setClosureAndLinearSpeed",
                entity_unique_id=f"{LOW_SPEED_URL}_low_speed",
                parameters=(65, OverkizCommandParam.LOWSPEED),
            ),
            35,
        ),
    ],
    ids=["roller-shutter", "awning", "low-speed"],
)
async def test_cover_set_position(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    case: CoverCommandCase,
    position: int,
) -> None:
    """Test cover position services and mapping."""
    await setup_overkiz_integration(fixture=case.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, case.entity_unique_id or case.device_url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: position},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=case.device_url,
        command_name=case.command_name,
        parameters=case.parameters,
    )


async def test_cover_tilt_services(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test tilt services for a pergola from a full user setup."""
    await setup_overkiz_integration(fixture=FIXTURE_PERGOLA)

    # Real setup fixtures anonymize labels, so the stable device URL is the best
    # handle for selecting the specific cover we want to exercise.
    entity_id = get_entity_id(entity_registry, PERGOLA_URL)
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
    assert get_state(hass, entity_id).state == CoverState.OPENING
    assert_command_call(
        mock_client,
        device_url=PERGOLA_URL,
        command_name="openSlats",
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=PERGOLA_URL,
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED.value,
            )
        ],
    )

    mock_client.execute_command.reset_mock()
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER_TILT,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert get_state(hass, entity_id).state == CoverState.CLOSING
    assert_command_call(
        mock_client,
        device_url=PERGOLA_URL,
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
        device_url=PERGOLA_URL,
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
        device_url=PERGOLA_URL,
        command_name="setOrientation",
        parameters=(60,),
    )


async def test_low_speed_cover_entities(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a low-speed shutter creates both standard and low-speed entities."""
    await setup_overkiz_integration(fixture=FIXTURE_LOW_SPEED)

    standard_entity_id = get_entity_id(entity_registry, LOW_SPEED_URL)
    low_speed_entity_id = get_entity_id(entity_registry, f"{LOW_SPEED_URL}_low_speed")

    assert hass.states.get(standard_entity_id)
    assert hass.states.get(low_speed_entity_id)

    standard = entity_registry.async_get(standard_entity_id)
    low_speed = entity_registry.async_get(low_speed_entity_id)
    assert standard is not None
    assert low_speed is not None
    assert standard.unique_id == LOW_SPEED_URL
    assert low_speed.unique_id == f"{LOW_SPEED_URL}_low_speed"


async def test_multiple_same_type_entities_have_distinct_unique_ids(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test repeated shutters from one setup keep distinct identities."""
    await setup_overkiz_integration(fixture=FIXTURE_LOW_SPEED)

    first_entity_id = get_entity_id(entity_registry, LOW_SPEED_URL)
    second_entity_id = get_entity_id(entity_registry, LOW_SPEED_OTHER_URL)
    first_entry = entity_registry.async_get(first_entity_id)
    second_entry = entity_registry.async_get(second_entity_id)
    assert first_entry is not None
    assert second_entry is not None
    assert first_entry.unique_id != second_entry.unique_id
    assert hass.states.get(first_entity_id)
    assert hass.states.get(second_entity_id)


async def test_tilt_only_cover_supported_features(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the pergola only exposes tilt controls."""
    await setup_overkiz_integration(fixture=FIXTURE_PERGOLA)

    state = get_state(hass, get_entity_id(entity_registry, PERGOLA_URL))
    assert state.attributes[ATTR_CURRENT_TILT_POSITION] == 0
    assert ATTR_CURRENT_POSITION not in state.attributes
    assert state.attributes["supported_features"] == (
        CoverEntityFeature.OPEN_TILT
        | CoverEntityFeature.CLOSE_TILT
        | CoverEntityFeature.STOP_TILT
        | CoverEntityFeature.SET_TILT_POSITION
    )


async def test_cover_position_update_on_poll(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover state updates after coordinator refresh."""
    await setup_overkiz_integration(fixture=FIXTURE_SHUTTERS_AND_GARAGE)

    entity_id = get_entity_id(entity_registry, SHUTTER_URL)
    assert get_state(hass, entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER_URL,
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

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER_URL,
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


async def test_cover_unavailable(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover unavailability propagates to the entity state."""
    await setup_overkiz_integration(fixture=FIXTURE_SHUTTERS_AND_GARAGE)

    entity_id = get_entity_id(entity_registry, SHUTTER_URL)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [build_event(EventName.DEVICE_UNAVAILABLE.value, device_url=SHUTTER_URL)],
    )

    assert get_state(hass, entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("fixture", "unique_id", "expected_state", "expected_closed"),
    [
        (FIXTURE_SHUTTERS_AND_GARAGE, GARAGE_URL, CoverState.CLOSED, True),
        (FIXTURE_PERGOLA, PERGOLA_URL, CoverState.CLOSED, True),
        (FIXTURE_RTS, RTS_URL, STATE_UNKNOWN, None),
    ],
    ids=["open-closed-unknown", "tilt-fallback", "unknown-rts"],
)
async def test_cover_is_closed_fallbacks(
    hass: HomeAssistant,
    setup_overkiz_integration,
    entity_registry: er.EntityRegistry,
    fixture: str,
    unique_id: str,
    expected_state: str,
    expected_closed: bool | None,
) -> None:
    """Test is_closed fallback order via entity state."""
    await setup_overkiz_integration(fixture=fixture)

    state = get_state(hass, get_entity_id(entity_registry, unique_id))
    assert state.state == expected_state
    assert state.attributes["is_closed"] is expected_closed


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
async def test_vertical_cover_movement_state_fallback(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving state fallback for vertical covers."""
    await setup_overkiz_integration(fixture=FIXTURE_SHUTTERS_AND_GARAGE)

    entity_id = get_entity_id(entity_registry, SHUTTER_URL)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER_URL,
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
async def test_awning_movement_state_fallback(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving state fallback for awnings."""
    await setup_overkiz_integration(fixture=FIXTURE_AWNING)

    entity_id = get_entity_id(entity_registry, AWNING_URL)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=AWNING_URL,
                device_states=device_states,
            )
        ],
    )

    assert get_state(hass, entity_id).state == expected_state


async def test_execution_tracking_sets_opening_state(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test execution tracking keeps the cover opening until completion."""
    await setup_overkiz_integration(fixture=FIXTURE_SHUTTERS_AND_GARAGE)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, SHUTTER_URL)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    assert get_state(hass, entity_id).state == CoverState.OPENING

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER_URL,
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
                device_url=SHUTTER_URL,
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED.value,
            )
        ],
    )

    assert get_state(hass, entity_id).state == CoverState.OPEN


async def test_awning_direct_position_mapping(
    hass: HomeAssistant,
    setup_overkiz_integration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test awning deployment uses direct mapping while vertical covers invert."""
    await setup_overkiz_integration(fixture=FIXTURE_AWNING)

    entity_id = get_entity_id(entity_registry, AWNING_URL)
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
        device_url=AWNING_URL,
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
                device_url=AWNING_URL,
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
