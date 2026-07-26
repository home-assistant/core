"""Tests for the Overkiz cover platform."""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import patch

from aiohttp import ClientConnectorError, ServerDisconnectedError
from freezegun.api import FrozenDateTimeFactory
from pyoverkiz.enums import ExecutionState, OverkizCommandParam, OverkizState
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
from homeassistant.components.overkiz import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er

from .conftest import FixtureDevice, MockOverkizClient, SetupOverkizIntegration
from .helpers import (
    assert_command_call,
    async_deliver_events,
    device_state_changed_event,
    device_unavailable_event,
    execution_state_changed_event,
)

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
    "cover.office_garden_house_shutter",
)
GARAGE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/1166863",
    "cover.living_room_main_garage_door",
)
TILTED_WINDOW = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_3.json",
    "io://1234-5678-9373/10202865",
    "cover.main_bedroom_bedroom_blinds",
)
# Device with ClosureState=108
DYNAMIC_EXTERIOR_VENETIAN_BLIND = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe.json",
    "io://1234-5678-6508/4877511",
    "cover.office_blinds",
)
# Device with ClosureState=124
POSITIONABLE_ROLLER_SHUTTER_UNO = FixtureDevice(
    "setup/local_somfy_tahoma_switch_europe_2.json",
    "io://1234-5678-1516/3656107",
    "cover.maple_residence_hallway_shutter",
)
POSITIONABLE_DUAL_ROLLER_SHUTTER = FixtureDevice(
    "setup/cloud_somfy_tahoma_switch_sc_europe.json",
    "io://1234-5678-5010/12931361",
    "cover.veranda_basement_roller_shutter",
)
TILT_ONLY_VENETIAN_BLIND = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16730044",
    "cover.palm_court_jaloezie",
)
UP_DOWN_VENETIAN_BLIND = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16747291",
    "cover.palm_court_office_venetian_blind",
)
UP_DOWN_SHEER_SCREEN = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16753206",
    "cover.palm_court_kitchen_sheer_screen",
)
# RTSGeneric only exposes raw up/down/stop commands (no open/close)
RTS_GENERIC = FixtureDevice(
    "setup/cloud_somfy_connexoon_rts_asia.json",
    "rts://1234-1234-6362/16718220",
    "cover.palm_court_living_room_screen",
)
DISCRETE_GARAGE_DOOR = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "io://1234-5678-3293/12745774",
    "cover.garage_door_rollixo",
)
DYNAMIC_GARAGE_DOOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16730050",
    "cover.living_room_garage_door",
)
DYNAMIC_GARAGE_DOOR_OGP = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/6632544",
    "cover.living_room_ogp_garage_door",
)
PARTIAL_GARAGE_DOOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/7433515",
    "cover.living_room_partial_garage_door",
)
RTS_GATE_4T = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "rts://1234-1234-6233/16730717",
    "cover.living_room_rts_gate",
)
RTS_GARAGE_DOOR_4T = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "rts://1234-1234-6233/16721270",
    "cover.living_room_rts_garage_door_4t",
)
CYCLIC_GARAGE_DOOR = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/6416929",
    "cover.living_room_cyclic_garage_door",
)
CYCLIC_SWINGING_GATE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-8983/1959462",
    "cover.living_room_swinging_gate",
)
SLIDING_DISCRETE_GATE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/16730051",
    "cover.living_room_sliding_gate",
)
DYNAMIC_GATE = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/10410217",
    "cover.living_room_ogp_gate",
)
DYNAMIC_PERGOLA = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/14356699",
    "cover.living_room_somfy_pergola",
)
DYNAMIC_PERGOLA_TILT_ONLY = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/10943109",
    "cover.living_room_bioclimatic_pergola",
)
PERGOLA_HORIZONTAL_AWNING = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "io://1234-1234-6233/11447718",
    "cover.living_room_pergola_awning",
)
DYNAMIC_VENETIAN_BLIND = FixtureDevice(
    "setup/cloud_somfy_tahoma_v2_europe.json",
    "ogp://1234-1234-6233/16730100",
    "cover.main_bedroom_bedroom_venetian_blind",
)
POSITIONABLE_VENETIAN_BLIND = FixtureDevice(
    "setup/local_somfy_tahoma_v2_europe.json",
    "zigbee://1234-5678-3293/16730099",
    "cover.living_room_venetian_blind",
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
        (DISCRETE_GARAGE_DOOR, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_GARAGE_DOOR, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_GARAGE_DOOR_OGP, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_GATE, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (RTS_GATE_4T, SERVICE_OPEN_COVER, "cycle", None, CoverState.OPENING),
        (RTS_GARAGE_DOOR_4T, SERVICE_OPEN_COVER, "cycle", None, CoverState.OPENING),
        (CYCLIC_GARAGE_DOOR, SERVICE_OPEN_COVER, "cycle", None, CoverState.OPENING),
        (CYCLIC_SWINGING_GATE, SERVICE_OPEN_COVER, "cycle", None, CoverState.OPENING),
        (SLIDING_DISCRETE_GATE, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (PARTIAL_GARAGE_DOOR, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (DYNAMIC_PERGOLA, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (
            PERGOLA_HORIZONTAL_AWNING,
            SERVICE_OPEN_COVER,
            "deploy",
            None,
            CoverState.OPENING,
        ),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_OPEN_COVER,
            "open",
            None,
            CoverState.OPENING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_OPEN_COVER,
            "open",
            None,
            CoverState.OPENING,
        ),
        (UP_DOWN_VENETIAN_BLIND, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (UP_DOWN_SHEER_SCREEN, SERVICE_OPEN_COVER, "open", None, CoverState.OPENING),
        (RTS_GENERIC, SERVICE_OPEN_COVER, "up", None, CoverState.OPENING),
        (
            DYNAMIC_VENETIAN_BLIND,
            SERVICE_OPEN_COVER,
            "open",
            None,
            CoverState.OPENING,
        ),
        (SHUTTER, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (AWNING, SERVICE_CLOSE_COVER, "undeploy", None, CoverState.CLOSING),
        (GARAGE, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (DISCRETE_GARAGE_DOOR, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (DYNAMIC_GARAGE_DOOR, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (
            DYNAMIC_GARAGE_DOOR_OGP,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (DYNAMIC_GATE, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        # Cycle command is used for both open and close; device reports OPENING
        # since the RTS protocol has no directional feedback.
        (RTS_GATE_4T, SERVICE_CLOSE_COVER, "cycle", None, CoverState.OPENING),
        (RTS_GARAGE_DOOR_4T, SERVICE_CLOSE_COVER, "cycle", None, CoverState.OPENING),
        (CYCLIC_GARAGE_DOOR, SERVICE_CLOSE_COVER, "cycle", None, CoverState.OPENING),
        (CYCLIC_SWINGING_GATE, SERVICE_CLOSE_COVER, "cycle", None, CoverState.OPENING),
        (SLIDING_DISCRETE_GATE, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (PARTIAL_GARAGE_DOOR, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (DYNAMIC_PERGOLA, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (
            PERGOLA_HORIZONTAL_AWNING,
            SERVICE_CLOSE_COVER,
            "undeploy",
            None,
            CoverState.CLOSING,
        ),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (
            UP_DOWN_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (UP_DOWN_SHEER_SCREEN, SERVICE_CLOSE_COVER, "close", None, CoverState.CLOSING),
        (RTS_GENERIC, SERVICE_CLOSE_COVER, "down", None, CoverState.CLOSING),
        (
            DYNAMIC_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER,
            "close",
            None,
            CoverState.CLOSING,
        ),
        (SHUTTER, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (AWNING, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (GARAGE, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DISCRETE_GARAGE_DOOR, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_GARAGE_DOOR, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_GARAGE_DOOR_OGP, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_GATE, SERVICE_STOP_COVER, "stop", None, CoverState.OPEN),
        (SLIDING_DISCRETE_GATE, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (PARTIAL_GARAGE_DOOR, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (DYNAMIC_PERGOLA, SERVICE_STOP_COVER, "stop", None, CoverState.CLOSED),
        (
            PERGOLA_HORIZONTAL_AWNING,
            SERVICE_STOP_COVER,
            "stop",
            None,
            CoverState.OPEN,
        ),
        (
            UP_DOWN_BIOCLIMATIC_PERGOLA,
            SERVICE_STOP_COVER,
            "stop",
            None,
            STATE_UNKNOWN,
        ),
        (TILT_ONLY_VENETIAN_BLIND, SERVICE_STOP_COVER, "stop", None, STATE_UNKNOWN),
        (
            DYNAMIC_VENETIAN_BLIND,
            SERVICE_STOP_COVER,
            "stop",
            None,
            CoverState.CLOSED,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_OPEN_COVER_TILT,
            "tiltPositive",
            [5],
            CoverState.OPENING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER_TILT,
            "tiltNegative",
            [5],
            CoverState.CLOSING,
        ),
        (
            TILT_ONLY_VENETIAN_BLIND,
            SERVICE_STOP_COVER_TILT,
            "stop",
            None,
            STATE_UNKNOWN,
        ),
        (UP_DOWN_VENETIAN_BLIND, SERVICE_STOP_COVER, "stop", None, STATE_UNKNOWN),
        (UP_DOWN_SHEER_SCREEN, SERVICE_STOP_COVER, "stop", None, STATE_UNKNOWN),
        (RTS_GENERIC, SERVICE_STOP_COVER, "stop", None, STATE_UNKNOWN),
        (
            UP_DOWN_VENETIAN_BLIND,
            SERVICE_OPEN_COVER_TILT,
            "tiltPositive",
            [5],
            CoverState.OPENING,
        ),
        (
            UP_DOWN_VENETIAN_BLIND,
            SERVICE_CLOSE_COVER_TILT,
            "tiltNegative",
            [5],
            CoverState.CLOSING,
        ),
        (
            UP_DOWN_VENETIAN_BLIND,
            SERVICE_STOP_COVER_TILT,
            "stop",
            None,
            STATE_UNKNOWN,
        ),
        (
            UP_DOWN_SHEER_SCREEN,
            SERVICE_OPEN_COVER_TILT,
            "tiltPositive",
            [5],
            CoverState.OPENING,
        ),
        (
            UP_DOWN_SHEER_SCREEN,
            SERVICE_CLOSE_COVER_TILT,
            "tiltNegative",
            [5],
            CoverState.CLOSING,
        ),
        (
            UP_DOWN_SHEER_SCREEN,
            SERVICE_STOP_COVER_TILT,
            "stop",
            None,
            STATE_UNKNOWN,
        ),
    ],
    ids=[
        "open-roller-shutter",
        "open-awning",
        "open-garage-door",
        "open-discrete-garage-door",
        "open-dynamic-garage-door",
        "open-dynamic-garage-door-ogp",
        "open-dynamic-gate",
        "open-rts-gate-4t",
        "open-rts-garage-door-4t",
        "open-cyclic-garage-door",
        "open-cyclic-swinging-gate",
        "open-sliding-discrete-gate",
        "open-partial-garage-door",
        "open-dynamic-pergola",
        "open-pergola-horizontal-awning",
        "open-up-down-bioclimatic-pergola",
        "open-tilt-only-venetian-blind",
        "open-venetian-blind-rts",
        "open-sheer-screen-rts",
        "open-rts-generic",
        "open-dynamic-venetian-blind",
        "close-roller-shutter",
        "close-awning",
        "close-garage-door",
        "close-discrete-garage-door",
        "close-dynamic-garage-door",
        "close-dynamic-garage-door-ogp",
        "close-dynamic-gate",
        "close-rts-gate-4t",
        "close-rts-garage-door-4t",
        "close-cyclic-garage-door",
        "close-cyclic-swinging-gate",
        "close-sliding-discrete-gate",
        "close-partial-garage-door",
        "close-dynamic-pergola",
        "close-pergola-horizontal-awning",
        "close-up-down-bioclimatic-pergola",
        "close-tilt-only-venetian-blind",
        "close-venetian-blind-rts",
        "close-sheer-screen-rts",
        "close-rts-generic",
        "close-dynamic-venetian-blind",
        "stop-roller-shutter",
        "stop-awning",
        "stop-garage-door",
        "stop-discrete-garage-door",
        "stop-dynamic-garage-door",
        "stop-dynamic-garage-door-ogp",
        "stop-dynamic-gate",
        "stop-sliding-discrete-gate",
        "stop-partial-garage-door",
        "stop-dynamic-pergola",
        "stop-pergola-horizontal-awning",
        "stop-up-down-bioclimatic-pergola",
        "stop-tilt-only-venetian-blind",
        "stop-dynamic-venetian-blind",
        "open-tilt-tilt-only-venetian-blind",
        "close-tilt-tilt-only-venetian-blind",
        "stop-tilt-tilt-only-venetian-blind",
        "stop-venetian-blind-rts",
        "stop-sheer-screen-rts",
        "stop-rts-generic",
        "open-tilt-venetian-blind-rts",
        "close-tilt-venetian-blind-rts",
        "stop-tilt-venetian-blind-rts",
        "open-tilt-sheer-screen-rts",
        "close-tilt-sheer-screen-rts",
        "stop-tilt-sheer-screen-rts",
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


async def test_merged_action_groups_keep_per_device_tracking(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that covers sharing a merged execution each keep their movement state.

    The action queue can merge concurrent action groups into one execution and
    return the same exec_id to every caller. Both covers must therefore report
    OPENING, and both must clear once that execution completes.
    """
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    # Both action groups merge into one execution sharing a single exec_id.
    mock_client.execute_action_group.side_effect = None
    mock_client.execute_action_group.return_value = "merged-exec"

    for device in (SHUTTER, GARAGE):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: device.entity_id},
            blocking=True,
        )
    await hass.async_block_till_done()

    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPENING
    assert hass.states.get(GARAGE.entity_id).state == CoverState.OPENING

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            execution_state_changed_event(
                exec_id="merged-exec",
                new_state=ExecutionState.COMPLETED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ],
    )

    assert hass.states.get(SHUTTER.entity_id).state == CoverState.CLOSED
    assert hass.states.get(GARAGE.entity_id).state == CoverState.CLOSED


@pytest.mark.parametrize(
    "exception",
    [
        TimeoutError("Connection timeout to host"),
        ClientConnectorError(None, OSError()),
        ServerDisconnectedError(),
    ],
    ids=["timeout", "client-connector", "server-disconnected"],
)
async def test_cover_command_connection_error_raises(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    exception: Exception,
) -> None:
    """Test that connection failures while sending a command raise HomeAssistantError."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    mock_client.execute_action_group.side_effect = exception

    with pytest.raises(HomeAssistantError, match="Failed to connect"):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_CLOSE_COVER,
            {ATTR_ENTITY_ID: SHUTTER.entity_id},
            blocking=True,
        )


@pytest.mark.parametrize(
    ("device", "entity_id", "command_name", "parameters", "position"),
    [
        (SHUTTER, SHUTTER.entity_id, "setClosure", [75], 25),
        (AWNING, AWNING.entity_id, "setDeployment", [80], 80),
        (
            LOW_SPEED,
            "cover.maple_residence_nursery_shutter_low_speed",
            "setClosureAndLinearSpeed",
            [65, OverkizCommandParam.LOWSPEED],
            35,
        ),
        (DYNAMIC_PERGOLA, DYNAMIC_PERGOLA.entity_id, "setClosure", [60], 40),
        (
            PERGOLA_HORIZONTAL_AWNING,
            PERGOLA_HORIZONTAL_AWNING.entity_id,
            "setDeployment",
            [80],
            80,
        ),
        (
            DYNAMIC_VENETIAN_BLIND,
            DYNAMIC_VENETIAN_BLIND.entity_id,
            "setClosure",
            [75],
            25,
        ),
    ],
    ids=[
        "roller-shutter",
        "awning",
        "low-speed",
        "dynamic-pergola",
        "pergola-horizontal-awning",
        "dynamic-venetian-blind",
    ],
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


@pytest.mark.parametrize(
    ("device", "command_name", "parameters", "tilt_position"),
    [
        (PERGOLA, "setOrientation", [60], 40),
        (DYNAMIC_PERGOLA_TILT_ONLY, "setOrientation", [60], 40),
    ],
    ids=[
        "bioclimatic-pergola",
        "dynamic-pergola-tilt-only",
    ],
)
async def test_cover_set_tilt_position(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    device: FixtureDevice,
    command_name: str,
    parameters: list[Any],
    tilt_position: int,
) -> None:
    """Test cover tilt position services and mapping."""
    await setup_overkiz_integration(fixture=device.fixture)

    await hass.services.async_call(
        COVER_DOMAIN,
        SERVICE_SET_COVER_TILT_POSITION,
        {ATTR_ENTITY_ID: device.entity_id, ATTR_TILT_POSITION: tilt_position},
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=device.device_url,
        command_name=command_name,
        parameters=parameters,
    )


async def test_is_closed_falls_back_to_position(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test is_closed derives from position when OpenClosedState is absent."""
    await setup_overkiz_integration(fixture=POSITIONABLE_VENETIAN_BLIND.fixture)

    state = hass.states.get(POSITIONABLE_VENETIAN_BLIND.entity_id)
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
                device_url=POSITIONABLE_VENETIAN_BLIND.device_url,
                device_states=[
                    {
                        "name": OverkizState.CORE_CLOSURE.value,
                        "type": 1,
                        "value": 50,
                    },
                ],
            )
        ],
    )

    state = hass.states.get(POSITIONABLE_VENETIAN_BLIND.entity_id)
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


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

    mock_client.execute_action_group.reset_mock()
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
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ],
    )
    assert hass.states.get(PERGOLA.entity_id).state == CoverState.CLOSED

    mock_client.execute_action_group.reset_mock()
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

    mock_client.execute_action_group.reset_mock()
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

    mock_client.execute_action_group.reset_mock()
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
            device_state_changed_event(
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
            device_state_changed_event(
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
            device_state_changed_event(
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
            execution_state_changed_event(
                exec_id="exec-1",
                new_state=ExecutionState.COMPLETED,
                old_state=ExecutionState.IN_PROGRESS,
            )
        ],
    )
    assert hass.states.get(SHUTTER.entity_id).state == CoverState.OPEN

    # Unavailability propagates to entity state
    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [device_unavailable_event(device_url=SHUTTER.device_url)],
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
    """Test moving direction detection for vertical covers."""
    await setup_overkiz_integration(fixture=SHUTTER.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
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
    """Test moving direction detection for awnings."""
    await setup_overkiz_integration(fixture=AWNING.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
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

    mock_client.execute_action_group.reset_mock()
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
            device_state_changed_event(
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
    """Test is_opening/is_closing None when states missing."""
    await setup_overkiz_integration(fixture=PERGOLA.fixture)

    await async_deliver_events(
        hass,
        freezer,
        mock_client,
        [
            device_state_changed_event(
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
            device_state_changed_event(
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
            device_state_changed_event(
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
    entity_id = "cover.maple_residence_nursery_shutter_low_speed"

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

    mock_client.execute_action_group.reset_mock()
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


async def test_set_cover_position_and_tilt_service_is_registered(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
) -> None:
    """The overkiz.set_cover_position_and_tilt service must be registered."""
    await setup_overkiz_integration(fixture=DYNAMIC_EXTERIOR_VENETIAN_BLIND.fixture)

    assert hass.services.has_service("overkiz", "set_cover_position_and_tilt")


async def test_set_cover_position_and_tilt_executes_single_command(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Position+tilt must be sent as one atomic setClosureAndOrientation call.

    Replaces two sequential set_cover_position + set_cover_tilt_position calls,
    which cause Somfy motors to stop mid-movement between commands.
    """
    await setup_overkiz_integration(fixture=DYNAMIC_EXTERIOR_VENETIAN_BLIND.fixture)

    await hass.services.async_call(
        DOMAIN,
        "set_cover_position_and_tilt",
        {
            ATTR_ENTITY_ID: DYNAMIC_EXTERIOR_VENETIAN_BLIND.entity_id,
            ATTR_POSITION: 30,
            ATTR_TILT_POSITION: 80,
        },
        blocking=True,
    )

    # Home Assistant position 30 -> Overkiz closure 70 (inverted),
    # tilt 80 -> orientation 20 (inverted).
    assert_command_call(
        mock_client,
        device_url=DYNAMIC_EXTERIOR_VENETIAN_BLIND.device_url,
        command_name="setClosureAndOrientation",
        parameters=[70, 20],
    )


@pytest.mark.parametrize(
    ("position", "tilt_position", "expected_parameters"),
    [
        (0, 100, [100, 0]),
        (100, 0, [0, 100]),
        (50, 50, [50, 50]),
    ],
    ids=["closed-tilt-open", "open-tilt-closed", "midpoint"],
)
async def test_set_cover_position_and_tilt_inverts_boundaries(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
    position: int,
    tilt_position: int,
    expected_parameters: list[int],
) -> None:
    """Boundary and midpoint values must invert consistently."""
    await setup_overkiz_integration(fixture=DYNAMIC_EXTERIOR_VENETIAN_BLIND.fixture)

    await hass.services.async_call(
        DOMAIN,
        "set_cover_position_and_tilt",
        {
            ATTR_ENTITY_ID: DYNAMIC_EXTERIOR_VENETIAN_BLIND.entity_id,
            ATTR_POSITION: position,
            ATTR_TILT_POSITION: tilt_position,
        },
        blocking=True,
    )

    assert_command_call(
        mock_client,
        device_url=DYNAMIC_EXTERIOR_VENETIAN_BLIND.device_url,
        command_name="setClosureAndOrientation",
        parameters=expected_parameters,
    )


async def test_set_cover_position_and_tilt_unsupported_command_raises(
    hass: HomeAssistant,
    setup_overkiz_integration: SetupOverkizIntegration,
    mock_client: MockOverkizClient,
) -> None:
    """Error raised when SET_CLOSURE_AND_ORIENTATION is missing.

    Defence-in-depth: even when a cover advertises both SET_POSITION and
    SET_TILT_POSITION (so it passes the ``required_features`` filter), the
    handler still checks the atomic command and aborts cleanly if it is
    missing.
    """
    # DYNAMIC_VENETIAN_BLIND supports setClosure and setOrientation (so it passes
    # the SET_POSITION | SET_TILT_POSITION required_features filter) but not the
    # atomic setClosureAndOrientation command, exactly the case this guard handles.
    await setup_overkiz_integration(fixture=DYNAMIC_VENETIAN_BLIND.fixture)

    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "set_cover_position_and_tilt",
            {
                ATTR_ENTITY_ID: DYNAMIC_VENETIAN_BLIND.entity_id,
                ATTR_POSITION: 50,
                ATTR_TILT_POSITION: 50,
            },
            blocking=True,
        )

    assert mock_client.execute_action_group.await_count == 0
