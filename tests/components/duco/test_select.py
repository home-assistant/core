"""Tests for the Duco select platform."""

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
import pytest

from homeassistant.components.select import (
    ATTR_OPTION,
    ATTR_OPTIONS,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import setup_platform_integration

from tests.common import MockConfigEntry

_SELECT_ENTITY = "select.living_ventilation_state"
_VALVE_SELECT_ENTITY = "select.bedroom_valve_ventilation_state"
_UNSUPPORTED_SELECT_ENTITY = "select.office_co2_ventilation_state"


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
    mock_nodes = [
        replace(
            mock_sensor_nodes[0],
            general=replace(mock_sensor_nodes[0].general, node_type=valve_node_type),
        ),
        *mock_sensor_nodes[1:],
    ]
    mock_duco_client.async_get_nodes.return_value = mock_nodes
    mock_duco_client.async_get_node_actions.return_value = _build_multi_node_actions(
        [node.node_id for node in mock_nodes],
        options=["AUTO", "CNT1", "CNT2", "CNT3", "MAN1", "MAN2", "MAN3"],
    )

    await setup_platform_integration(hass, mock_config_entry, [Platform.SELECT])

    assert hass.states.get(_SELECT_ENTITY) is not None
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

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _SELECT_ENTITY, ATTR_OPTION: "CNT2"},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "CNT2")


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
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: _SELECT_ENTITY, ATTR_OPTION: "CNT2"},
            blocking=True,
        )


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

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _SELECT_ENTITY, ATTR_OPTION: "MAN1x2"},
        blocking=True,
    )

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

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: _SELECT_ENTITY, ATTR_OPTION: "AUTO"},
        blocking=True,
    )

    mock_duco_client.async_set_ventilation_state.assert_called_once_with(1, "AUTO")
    state = hass.states.get(_SELECT_ENTITY)
    assert state is not None
    assert state.state == "CNT1"


async def test_select_entity_is_added_when_action_discovery_succeeds_later(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> None:
    """Test select entities are added when action discovery becomes available later."""
    mock_duco_client.async_get_node_actions.side_effect = [
        DucoConnectionError("Connection refused"),
        _build_node_actions(
            options=["AUTO", "CNT1", "CNT2", "CNT3", "MAN1", "MAN2", "MAN3"]
        ),
    ]

    config_entry = await setup_platform_integration(
        hass, mock_config_entry, [Platform.SELECT]
    )

    assert hass.states.get(_SELECT_ENTITY) is None

    await config_entry.runtime_data.async_refresh()
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
