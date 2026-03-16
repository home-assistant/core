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
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import MockOverkizClient, SetupOverkizIntegration
from .helpers import assert_command_call, async_deliver_events, build_event

from tests.common import snapshot_platform


class FixtureDevice(NamedTuple):
    """Test device binding a fixture file to a device URL."""

    fixture: str
    url: str


AWNING = FixtureDevice("setup/setup_local.json", "io://1234-1234-1234/5928357")
LOW_SPEED = FixtureDevice("setup/setup_nexity_2.json", "io://1234-5678-1698/141613")
LOW_SPEED_OTHER = FixtureDevice(
    "setup/setup_nexity_2.json", "io://1234-5678-1698/4080031"
)
PERGOLA = FixtureDevice("setup/setup_local_tahoma.json", "io://1234-5678-3293/7614902")
RTS = FixtureDevice("setup/setup_hi_kumo.json", "rts://1234-1234-6362/16730022")
SHUTTER = FixtureDevice("setup/setup_tahoma_3.json", "io://1234-1234-6233/12184029")
GARAGE = FixtureDevice("setup/setup_tahoma_3.json", "io://1234-1234-6233/1166863")
TILTED_WINDOW = FixtureDevice(
    "setup/setup_local_with_climate.json", "io://1234-5678-9373/10202865"
)
# Device with ClosureState=108
DYNAMIC_EXTERIOR_VENETIAN_BLIND = FixtureDevice(
    "setup/setup_local_somfy_europe.json", "io://1234-5678-6508/4877511"
)

SNAPSHOT_FIXTURES = [
    AWNING,
    LOW_SPEED,
    PERGOLA,
    RTS,
    SHUTTER,
    TILTED_WINDOW,
    DYNAMIC_EXTERIOR_VENETIAN_BLIND,
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
    ("device", "command_name", "expected_state", "entity_unique_id"),
    [
        (SHUTTER, "open", CoverState.OPENING, None),
        (AWNING, "deploy", CoverState.CLOSED, None),
        (GARAGE, "open", CoverState.OPENING, None),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_open(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    command_name: str,
    expected_state: str,
    entity_unique_id: str | None,
) -> None:
    """Test opening supported covers via the service layer."""
    await setup_overkiz_integration(fixture=device.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, entity_unique_id or device.url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_OPEN_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert get_state(hass, entity_id).state == expected_state
    assert_command_call(
        mock_client,
        device_url=device.url,
        command_name=command_name,
    )


@pytest.mark.parametrize(
    ("device", "command_name", "expected_state", "entity_unique_id"),
    [
        (SHUTTER, "close", CoverState.CLOSING, None),
        (AWNING, "undeploy", CoverState.CLOSED, None),
        (GARAGE, "close", CoverState.CLOSING, None),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_close(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    command_name: str,
    expected_state: str,
    entity_unique_id: str | None,
) -> None:
    """Test closing supported covers via the service layer."""
    await setup_overkiz_integration(fixture=device.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, entity_unique_id or device.url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_CLOSE_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert get_state(hass, entity_id).state == expected_state
    assert_command_call(
        mock_client,
        device_url=device.url,
        command_name=command_name,
    )


@pytest.mark.parametrize(
    ("device", "command_name", "entity_unique_id"),
    [
        (SHUTTER, "stop", None),
        (AWNING, "stop", None),
        (GARAGE, "stop", None),
    ],
    ids=["roller-shutter", "awning", "garage-door"],
)
async def test_cover_stop(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    command_name: str,
    entity_unique_id: str | None,
) -> None:
    """Test stop commands for supported covers."""
    await setup_overkiz_integration(fixture=device.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, entity_unique_id or device.url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_STOP_COVER,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.url,
        command_name=command_name,
    )


@pytest.mark.parametrize(
    (
        "device",
        "command_name",
        "entity_unique_id",
        "parameters",
        "position",
    ),
    [
        (SHUTTER, "setClosure", None, (75,), 25),
        (AWNING, "setDeployment", None, (80,), 80),
        (
            LOW_SPEED,
            "setClosureAndLinearSpeed",
            f"{LOW_SPEED.url}_low_speed",
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
    entity_unique_id: str | None,
    parameters: tuple[Any, ...],
    position: int,
) -> None:
    """Test cover position services and mapping."""
    await setup_overkiz_integration(fixture=device.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, entity_unique_id or device.url)
    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_POSITION,
        {ATTR_ENTITY_ID: entity_id, ATTR_POSITION: position},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.url,
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

    entity_id = get_entity_id(entity_registry, PERGOLA.url)
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
        device_url=PERGOLA.url,
        command_name="openSlats",
    )

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.EXECUTION_STATE_CHANGED.value,
                device_url=PERGOLA.url,
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
        device_url=PERGOLA.url,
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
        device_url=PERGOLA.url,
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
        device_url=PERGOLA.url,
        command_name="setOrientation",
        parameters=(60,),
    )


async def test_low_speed_cover_entities(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a low-speed shutter creates both standard and low-speed entities."""
    await setup_overkiz_integration(fixture=LOW_SPEED.fixture)

    standard_entity_id = get_entity_id(entity_registry, LOW_SPEED.url)
    low_speed_entity_id = get_entity_id(entity_registry, f"{LOW_SPEED.url}_low_speed")

    assert hass.states.get(standard_entity_id)
    assert hass.states.get(low_speed_entity_id)

    standard = entity_registry.async_get(standard_entity_id)
    low_speed = entity_registry.async_get(low_speed_entity_id)
    assert standard is not None
    assert low_speed is not None
    assert standard.unique_id == LOW_SPEED.url
    assert low_speed.unique_id == f"{LOW_SPEED.url}_low_speed"


async def test_multiple_same_type_entities_have_distinct_unique_ids(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test repeated shutters from one setup keep distinct identities."""
    await setup_overkiz_integration(fixture=LOW_SPEED.fixture)

    first_entity_id = get_entity_id(entity_registry, LOW_SPEED.url)
    second_entity_id = get_entity_id(entity_registry, LOW_SPEED_OTHER.url)
    first_entry = entity_registry.async_get(first_entity_id)
    second_entry = entity_registry.async_get(second_entity_id)
    assert first_entry is not None
    assert second_entry is not None
    assert first_entry.unique_id != second_entry.unique_id
    assert hass.states.get(first_entity_id)
    assert hass.states.get(second_entity_id)


async def test_tilt_only_cover_supported_features(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that the pergola only exposes tilt controls."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    state = get_state(hass, get_entity_id(entity_registry, PERGOLA.url))
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
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover state updates after coordinator refresh."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entity_id = get_entity_id(entity_registry, SHUTTER.url)
    assert get_state(hass, entity_id).attributes[ATTR_CURRENT_POSITION] == 0

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.url,
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
                device_url=SHUTTER.url,
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
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test cover unavailability propagates to the entity state."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entity_id = get_entity_id(entity_registry, SHUTTER.url)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [build_event(EventName.DEVICE_UNAVAILABLE.value, device_url=SHUTTER.url)],
    )

    assert get_state(hass, entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("device", "expected_state", "expected_closed"),
    [
        (GARAGE, CoverState.CLOSED, True),
        (PERGOLA, CoverState.CLOSED, True),
        (RTS, STATE_UNKNOWN, None),
    ],
    ids=["open-closed-unknown", "tilt-fallback", "unknown-rts"],
)
async def test_cover_is_closed_fallbacks(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    entity_registry: er.EntityRegistry,
    device: FixtureDevice,
    expected_state: str,
    expected_closed: bool | None,
) -> None:
    """Test is_closed fallback order via entity state."""
    await setup_overkiz_integration(fixture=device.fixture)

    state = get_state(hass, get_entity_id(entity_registry, device.url))
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
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving state fallback for vertical covers."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    entity_id = get_entity_id(entity_registry, SHUTTER.url)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=SHUTTER.url,
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
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
    device_states: list[dict[str, Any]],
    expected_state: CoverState,
) -> None:
    """Test moving state fallback for awnings."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    entity_id = get_entity_id(entity_registry, AWNING.url)
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            build_event(
                EventName.DEVICE_STATE_CHANGED.value,
                device_url=AWNING.url,
                device_states=device_states,
            )
        ],
    )

    assert get_state(hass, entity_id).state == expected_state


async def test_execution_tracking_sets_opening_state(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test execution tracking keeps the cover opening until completion."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)
    mock_client.execute_command.reset_mock()

    entity_id = get_entity_id(entity_registry, SHUTTER.url)
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
                device_url=SHUTTER.url,
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
                device_url=SHUTTER.url,
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED.value,
            )
        ],
    )

    assert get_state(hass, entity_id).state == CoverState.OPEN


async def test_awning_direct_position_mapping(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test awning deployment uses direct mapping while vertical covers invert."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    entity_id = get_entity_id(entity_registry, AWNING.url)
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
        device_url=AWNING.url,
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
                device_url=AWNING.url,
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
