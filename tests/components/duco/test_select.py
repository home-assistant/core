"""Tests for the Duco select platform."""

import asyncio
from dataclasses import replace
from unittest.mock import AsyncMock

from duco_connectivity import (
    ActionItem,
    ActionValueType,
    DucoConnectionError,
    DucoError,
    DucoRateLimitError,
    KnownActionName,
    Node,
    NodeActionItemList,
    NodeListActionItemList,
    NodeType,
    VentilationState,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.duco.const import SCAN_INTERVAL
from homeassistant.components.fan import (
    ATTR_PERCENTAGE,
    DOMAIN as FAN_DOMAIN,
    SERVICE_SET_PERCENTAGE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_platform_integration

from tests.common import MockConfigEntry, async_fire_time_changed

_SELECT_ENTITY = "select.living_ventilation_state"
_VALVE_SELECT_ENTITY = "select.bedroom_valve_ventilation_state"
_UNSUPPORTED_SELECT_ENTITY = "select.office_co2_ventilation_state"
# Node 50 "Kitchen RH" (a non-box satellite node) repurposed as a controllable node.
_CONTROLLABLE_SELECT_ENTITY = "select.kitchen_rh_ventilation_state"


def _build_node_actions(
    *,
    node_id: int = 1,
    options: list[str] | None = None,
) -> NodeListActionItemList:
    """Build node action discovery data for select tests."""
    return NodeListActionItemList(
        nodes=[
            NodeActionItemList(
                node_id=node_id,
                actions=[
                    ActionItem(
                        action=KnownActionName.SET_VENTILATION_STATE,
                        val_type=ActionValueType.ENUM,
                        enum_values=[] if options is None else options,
                    )
                ],
            )
        ]
    )


def _build_multi_node_actions(
    node_ids: list[int],
    *,
    options: list[str],
) -> NodeListActionItemList:
    """Build identical node action discovery data for multiple nodes."""
    return NodeListActionItemList(
        nodes=[
            NodeActionItemList(
                node_id=node_id,
                actions=[
                    ActionItem(
                        action=KnownActionName.SET_VENTILATION_STATE,
                        val_type=ActionValueType.ENUM,
                        enum_values=options,
                    )
                ],
            )
            for node_id in node_ids
        ]
    )


def _replace_node_state(node: Node, state: str | VentilationState | None) -> Node:
    """Return a copy of the node with an updated ventilation state."""
    if state is None:
        return replace(node, ventilation=None)

    assert node.ventilation is not None
    return replace(node, ventilation=replace(node.ventilation, state=state))


def _assert_select_state(hass: HomeAssistant, expected_state: str) -> None:
    """Assert the ventilation select state."""
    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.state == expected_state


async def _async_select_option(
    hass: HomeAssistant, option: str, entity_id: str = _SELECT_ENTITY
) -> None:
    """Select a ventilation option."""
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: option},
        blocking=True,
    )


async def _async_set_fan_percentage(hass: HomeAssistant) -> None:
    """Set the ventilation fan percentage."""
    await hass.services.async_call(
        FAN_DOMAIN,
        SERVICE_SET_PERCENTAGE,
        {ATTR_ENTITY_ID: "fan.living", ATTR_PERCENTAGE: 33},
        blocking=True,
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up only the select platform for testing."""
    return await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])


@pytest.mark.usefixtures("init_integration")
async def test_select_entity_created_with_dynamic_options(
    hass: HomeAssistant,
) -> None:
    """Test that select entities are created only for nodes with usable actions."""
    state = hass.states.get(_SELECT_ENTITY)

    assert state is not None
    assert state.state == "AUTO"
    assert state.attributes[ATTR_OPTIONS] == [
        "AUTO",
        "CNT1",
        "CNT2",
        "CNT3",
        "MAN1",
        "MAN2",
        "MAN3",
    ]
    assert hass.states.get(_UNSUPPORTED_SELECT_ENTITY) is None


@pytest.mark.parametrize(
    "valve_node_type",
    [
        pytest.param(NodeType.VLV, id="vlv"),
        pytest.param(NodeType.VLVRH, id="vlvrh"),
        pytest.param(NodeType.VLVVOC, id="vlvvoc"),
        pytest.param(NodeType.VLVCO2, id="vlvco2"),
        pytest.param(NodeType.VLVCO2RH, id="vlvco2rh"),
        pytest.param(NodeType.EAV, id="eav"),
        pytest.param(NodeType.EAVRH, id="eavrh"),
        pytest.param(NodeType.EAVVOC, id="eavvoc"),
        pytest.param(NodeType.EAVCO2, id="eavco2"),
    ],
)
async def test_select_creates_entities_for_controllable_valve_nodes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    valve_node_type: NodeType,
) -> None:
    """Test select discovery includes valve nodes when they advertise control."""
    # Mutate a non-box node (node 50 "Kitchen RH", index 3); mutating the box
    # node would make its via_device link resolve to itself.
    mock_nodes = [
        *mock_sensor_nodes[:3],
        replace(
            mock_sensor_nodes[3],
            general=replace(mock_sensor_nodes[3].general, node_type=valve_node_type),
        ),
        *mock_sensor_nodes[4:],
    ]
    mock_duco_client.async_get_nodes.return_value = mock_nodes
    mock_duco_client.async_get_node_actions.return_value = _build_multi_node_actions(
        [node.node_id for node in mock_nodes],
        options=["AUTO", "CNT1", "CNT2", "CNT3", "MAN1", "MAN2", "MAN3"],
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    assert hass.states.get(_CONTROLLABLE_SELECT_ENTITY) is not None
    valve_state = hass.states.get(_VALVE_SELECT_ENTITY)
    assert valve_state is not None
    assert valve_state.attributes[ATTR_OPTIONS] == [
        "AUTO",
        "CNT1",
        "CNT2",
        "CNT3",
        "MAN1",
        "MAN2",
        "MAN3",
    ]
    assert hass.states.get(_UNSUPPORTED_SELECT_ENTITY) is None


@pytest.mark.usefixtures("init_integration")
async def test_select_option_calls_ventilation_state_library_method(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
) -> None:
    """Test that selecting an option uses the typed ventilation state helper."""
    mock_duco_client.async_set_ventilation_state = AsyncMock()

    await _async_select_option(hass, "CNT2")

    mock_duco_client.async_set_ventilation_state.assert_awaited_once_with(1, "CNT2")
    mock_duco_client.async_get_node_info.assert_awaited_once_with(1)
    assert mock_duco_client.async_get_nodes.await_count == 1


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    ("exception", "match"),
    [
        pytest.param(DucoError("Unexpected error"), "Failed to set ventilation state"),
        pytest.param(DucoRateLimitError(), "daily write limit"),
    ],
)
async def test_select_option_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    match: str,
) -> None:
    """Test that a HomeAssistantError is raised on select write failure."""
    mock_duco_client.async_set_ventilation_state = AsyncMock(side_effect=exception)

    with pytest.raises(HomeAssistantError, match=match):
        await _async_select_option(hass, "CNT2")


async def test_select_extended_manual_options_allow_normalized_readback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
) -> None:
    """Test extended manual actions can read back as the normalized manual state."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions(
        options=["AUTO", "MAN1", "MAN1x2", "MAN1x3"]
    )
    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == ["AUTO", "MAN1", "MAN1x2", "MAN1x3"]
    box_node = mock_nodes[0]
    mock_duco_client.async_set_ventilation_state = AsyncMock()
    mock_duco_client.async_get_nodes.return_value = [
        _replace_node_state(box_node, "MAN1"),
        *mock_nodes[1:],
    ]

    await _async_select_option(hass, "MAN1x2")

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "MAN1x2")
    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.state == "MAN1"


async def test_select_auto_option_allows_cnt1_readback(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
) -> None:
    """Test AUTO readback can normalize to CNT1 without treating it as an error."""
    mock_duco_client.async_get_node_actions.return_value = _build_node_actions(
        options=["AUTO", "CNT1", "CNT2"]
    )
    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])
    box_node = mock_nodes[0]
    mock_duco_client.async_set_ventilation_state = AsyncMock()
    mock_duco_client.async_get_nodes.return_value = [
        _replace_node_state(box_node, "CNT1"),
        *mock_nodes[1:],
    ]

    await _async_select_option(hass, "AUTO")

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "AUTO")
    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.state == "CNT1"


@pytest.mark.parametrize(
    ("failed_entity_id", "expected_state"),
    [
        pytest.param(_SELECT_ENTITY, "CNT1", id="same-node"),
        pytest.param(_VALVE_SELECT_ENTITY, STATE_UNAVAILABLE, id="other-node"),
    ],
)
async def test_targeted_readback_failure_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_sensor_nodes: list[Node],
    failed_entity_id: str,
    expected_state: str,
) -> None:
    """Test a targeted success only clears its own node's failure."""
    mock_duco_client.async_get_nodes.return_value = mock_sensor_nodes
    mock_duco_client.async_get_node_actions.return_value = _build_multi_node_actions(
        [1, 60], options=["AUTO", "CNT1", "MAN3"]
    )
    await setup_platform_integration(
        hass, mock_config_entry, [Platform.FAN, Platform.SELECT]
    )
    fan_write_started = asyncio.Event()
    release_fan_write = asyncio.Event()

    async def set_ventilation_state(
        node_id: int, state: str | VentilationState
    ) -> None:
        if state == "CNT1":
            fan_write_started.set()
            await release_fan_write.wait()

    mock_duco_client.async_set_ventilation_state.side_effect = set_ventilation_state
    mock_duco_client.async_get_node_info.side_effect = [
        DucoError("Readback failed"),
        _replace_node_state(mock_sensor_nodes[0], "CNT1"),
    ]

    fan_task = asyncio.create_task(_async_set_fan_percentage(hass))
    await fan_write_started.wait()

    await _async_select_option(hass, "MAN3", failed_entity_id)
    _assert_select_state(hass, STATE_UNAVAILABLE)

    release_fan_write.set()
    await fan_task

    _assert_select_state(hass, expected_state)


async def test_targeted_readback_restores_node_omitted_by_older_poll(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a targeted readback restores a node omitted by an older poll."""
    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])
    poll_started = asyncio.Event()
    release_poll = asyncio.Event()
    write_started = asyncio.Event()

    async def get_nodes() -> list[Node]:
        poll_started.set()
        await release_poll.wait()
        return mock_nodes[1:]

    def set_ventilation_state(node_id: int, state: str | VentilationState) -> None:
        write_started.set()

    mock_duco_client.async_get_nodes.side_effect = get_nodes
    mock_duco_client.async_set_ventilation_state.side_effect = set_ventilation_state
    mock_duco_client.async_get_node_info.return_value = _replace_node_state(
        mock_nodes[0], "MAN3"
    )
    mock_duco_client.async_get_node_info.side_effect = None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await poll_started.wait()

    write_task = asyncio.create_task(_async_select_option(hass, "MAN3"))
    await write_started.wait()

    release_poll.set()
    await write_task

    _assert_select_state(hass, "MAN3")


async def test_latest_targeted_readback_wins_when_fan_and_select_overlap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
) -> None:
    """Test an older fan readback cannot overwrite a newer select readback."""
    await setup_platform_integration(
        hass, mock_config_entry, [Platform.FAN, Platform.SELECT]
    )
    first_readback_started = asyncio.Event()
    release_first_readback = asyncio.Event()
    select_write_started = asyncio.Event()
    readback_count = 0

    def set_ventilation_state(node_id: int, state: str | VentilationState) -> None:
        if state == "MAN3":
            select_write_started.set()

    async def get_node_info(node_id: int) -> Node:
        nonlocal readback_count
        readback_count += 1
        if readback_count == 1:
            first_readback_started.set()
            await release_first_readback.wait()
            return _replace_node_state(mock_nodes[0], "CNT1")
        return _replace_node_state(mock_nodes[0], "MAN3")

    mock_duco_client.async_set_ventilation_state.side_effect = set_ventilation_state
    mock_duco_client.async_get_node_info.side_effect = get_node_info
    fan_task = asyncio.create_task(_async_set_fan_percentage(hass))
    await first_readback_started.wait()

    select_task = asyncio.create_task(_async_select_option(hass, "MAN3"))
    await select_write_started.wait()

    release_first_readback.set()
    await asyncio.gather(fan_task, select_task)

    _assert_select_state(hass, "MAN3")


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize(
    "readback_error",
    [
        pytest.param(None, id="success"),
        pytest.param(
            DucoError("Readback failed"),
            id="failure",
        ),
    ],
)
async def test_newer_coordinator_poll_supersedes_targeted_outcome(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    freezer: FrozenDateTimeFactory,
    readback_error: DucoError | None,
) -> None:
    """Test a newer coordinator poll supersedes an older targeted outcome."""
    readback_started = asyncio.Event()
    release_readback = asyncio.Event()

    async def get_node_info(node_id: int) -> Node:
        readback_started.set()
        await release_readback.wait()
        if readback_error:
            raise readback_error
        return _replace_node_state(mock_nodes[0], "MAN3")

    mock_duco_client.async_get_node_info.side_effect = get_node_info
    write_task = asyncio.create_task(_async_select_option(hass, "MAN3"))
    await readback_started.wait()

    mock_duco_client.async_get_nodes.return_value = [
        _replace_node_state(mock_nodes[0], "CNT2"),
        *mock_nodes[1:],
    ]
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)

    release_readback.set()
    await write_task
    await hass.async_block_till_done()

    _assert_select_state(hass, "CNT2")


async def test_select_entity_is_added_when_action_discovery_succeeds_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test select entities are added when action discovery becomes available later."""
    mock_duco_client.async_get_node_actions.side_effect = [
        DucoConnectionError("Connection refused"),
        _build_node_actions(
            options=["AUTO", "CNT1", "CNT2", "CNT3", "MAN1", "MAN2", "MAN3"]
        ),
    ]

    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    assert hass.states.get(_SELECT_ENTITY) is None

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.attributes[ATTR_OPTIONS] == [
        "AUTO",
        "CNT1",
        "CNT2",
        "CNT3",
        "MAN1",
        "MAN2",
        "MAN3",
    ]


@pytest.mark.parametrize(
    "node_actions",
    [
        pytest.param(
            NodeListActionItemList(nodes=[NodeActionItemList(node_id=1, actions=[])]),
            id="missing-action",
        ),
        pytest.param(
            _build_node_actions(options=None),
            id="missing-enum-values",
        ),
    ],
)
async def test_select_missing_action_metadata_does_not_crash(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    node_actions: NodeListActionItemList,
) -> None:
    """Test incomplete action discovery data does not create broken entities."""
    mock_duco_client.async_get_node_actions.return_value = node_actions

    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    state = hass.states.get(_SELECT_ENTITY)
    assert state is None


@pytest.mark.parametrize(
    "state",
    [
        pytest.param("SOMETHING_NEW", id="unknown-state"),
        pytest.param(None, id="missing-ventilation"),
    ],
)
async def test_select_unknown_or_missing_current_state_does_not_crash(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
    mock_nodes: list[Node],
    state: str | None,
) -> None:
    """Test missing or unknown current states stay safe in select properties."""
    mock_duco_client.async_get_nodes.return_value = [
        _replace_node_state(mock_nodes[0], state),
        *mock_nodes[1:],
    ]

    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    entity_state = hass.states.get(_SELECT_ENTITY)
    assert entity_state is not None
    assert entity_state.state == STATE_UNKNOWN
