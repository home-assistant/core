"""Fixtures for Duco tests."""

from collections.abc import Generator
from typing import Any
from unittest.mock import AsyncMock, patch

from duco_connectivity import (
    ActionItem,
    ActionValueType,
    ApiEndpointInfo,
    ApiInfo,
    BoardInfo,
    ConfigNode,
    ConfigNodeOverview,
    ConfigValueString,
    DiagComponent,
    KnownActionName,
    LanInfo,
    Node,
    NodeActionItemList,
    NodeGeneralInfo,
    NodeListActionItemList,
    NodeMotorStateInfo,
    NodeSensorInfo,
    NodeVentilationInfo,
)
import pytest

from homeassistant.components.duco.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry, load_json_array_fixture

TEST_HOST = "192.168.1.100"
TEST_MAC = "aa:bb:cc:dd:ee:ff"

USER_INPUT = {CONF_HOST: TEST_HOST}

UNSUPPORTED_BOARD_INFOS = [
    pytest.param(
        BoardInfo(
            box_name="SILENT_CONNECT",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version="2.0",
        ),
        id="version-too-low",
    ),
    pytest.param(
        BoardInfo(
            box_name="SILENT_CONNECT",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version=None,
        ),
        id="missing-version",
    ),
    pytest.param(
        BoardInfo(
            box_name="SILENT_CONNECT",
            box_sub_type_name="Eu",
            serial_board_box="ABC123",
            serial_board_comm="DEF456",
            serial_duco_box="GHI789",
            serial_duco_comm="JKL012",
            time=1700000000,
            public_api_version="2.1.0-beta",
        ),
        id="malformed-version",
    ),
]


def _node_from_dict(data: dict[str, Any]) -> Node:
    """Convert a node fixture payload into a Duco node model."""
    ventilation = data.get("ventilation")
    sensor = data.get("sensor")
    motor_state = data.get("motor_state")

    return Node(
        node_id=data["node_id"],
        general=NodeGeneralInfo(**data["general"]),
        ventilation=NodeVentilationInfo(**ventilation)
        if ventilation is not None
        else None,
        sensor=NodeSensorInfo(**sensor) if sensor is not None else None,
        motor_state=NodeMotorStateInfo(**motor_state)
        if motor_state is not None
        else None,
    )


def load_nodes_fixture(filename: str) -> list[Node]:
    """Load nodes from a JSON fixture file."""
    return [_node_from_dict(node) for node in load_json_array_fixture(filename, DOMAIN)]


def node_configs_from_nodes(nodes: list[Node]) -> ConfigNodeOverview:
    """Build node config names from node fixtures."""
    return ConfigNodeOverview(
        nodes=[
            ConfigNode(
                node_id=node.node_id,
                name=ConfigValueString(node.general.name),
            )
            for node in nodes
        ]
    )


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="SILENT_CONNECT",
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id=TEST_MAC,
    )


@pytest.fixture
def mock_board_info() -> BoardInfo:
    """Return mock board info."""
    return BoardInfo(
        box_name="SILENT_CONNECT",
        box_sub_type_name="Eu",
        serial_board_box="ABC123",
        serial_board_comm="DEF456",
        serial_duco_box="GHI789",
        serial_duco_comm="JKL012",
        time=1700000000,
        public_api_version="2.5",
        software_version="1.2.3",
    )


@pytest.fixture
def mock_api_info() -> ApiInfo:
    """Return mock API info."""
    return ApiInfo(
        api_version="2.5",
        reported_api_version="2.5.1",
        endpoints=[
            ApiEndpointInfo(
                url="/info",
                query_parameters=["module", "submodule"],
                methods=["GET"],
                modules=["General", "Diag"],
            )
        ],
    )


@pytest.fixture
def mock_lan_info() -> LanInfo:
    """Return mock LAN info."""
    return LanInfo(
        mode="WIFI_CLIENT",
        ip=TEST_HOST,
        net_mask="255.255.255.0",
        default_gateway="192.168.1.1",
        dns="8.8.8.8",
        mac=TEST_MAC,
        host_name="duco-box",
        rssi_wifi=-60,
    )


@pytest.fixture
def mock_nodes() -> list[Node]:
    """Return a list of nodes covering all supported types."""
    return load_nodes_fixture("nodes.json")


@pytest.fixture
def mock_node_actions() -> NodeListActionItemList:
    """Return node actions for supported ventilation control nodes."""
    return NodeListActionItemList(
        nodes=[
            NodeActionItemList(
                node_id=1,
                actions=[
                    ActionItem(
                        action=KnownActionName.SET_VENTILATION_STATE,
                        val_type=ActionValueType.ENUM,
                        enum_values=[
                            "AUTO",
                            "CNT1",
                            "CNT2",
                            "CNT3",
                            "MAN1",
                            "MAN2",
                            "MAN3",
                        ],
                    )
                ],
            ),
            NodeActionItemList(node_id=2, actions=[]),
            NodeActionItemList(node_id=50, actions=[]),
            NodeActionItemList(node_id=113, actions=[]),
        ]
    )


@pytest.fixture
def mock_sensor_nodes(mock_nodes: list[Node]) -> list[Node]:
    """Return sensor test nodes including VLV examples."""
    return [*mock_nodes, *load_nodes_fixture("sensor_nodes.json")]


@pytest.fixture
def dynamic_sensor_nodes() -> dict[int, Node]:
    """Return dynamic sensor test nodes keyed by node ID."""
    return {
        node.node_id: node for node in load_nodes_fixture("dynamic_sensor_nodes.json")
    }


@pytest.fixture
def mock_duco_client(
    mock_api_info: ApiInfo,
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_nodes: list[Node],
    mock_node_actions: NodeListActionItemList,
) -> Generator[AsyncMock]:
    """Return a mocked DucoClient used by both the integration and config flow."""
    with (
        patch(
            "homeassistant.components.duco.DucoClient",
            autospec=True,
        ) as mock_class,
        patch(
            "homeassistant.components.duco.config_flow.DucoClient",
            new=mock_class,
        ),
    ):
        client = mock_class.return_value
        client.async_get_api_info.return_value = mock_api_info
        client.async_get_board_info.return_value = mock_board_info
        client.async_get_lan_info.return_value = mock_lan_info
        client.async_get_nodes.return_value = mock_nodes
        client.async_get_node_configs.return_value = node_configs_from_nodes(mock_nodes)
        client.async_get_node_actions.return_value = mock_node_actions
        client.async_get_time_filter_remaining.return_value = 180
        client.async_get_diagnostics.return_value = [
            DiagComponent(component="Ventilation", status="Ok")
        ]
        client.async_get_write_requests_remaining.return_value = 100
        yield client


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.duco.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_duco_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the Duco integration for testing."""
    return await setup_integration(hass, mock_config_entry)
