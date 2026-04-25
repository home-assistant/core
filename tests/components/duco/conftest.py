"""Fixtures for Duco tests."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from duco.models import (
    BoardInfo,
    DiagComponent,
    DiagStatus,
    LanInfo,
    Node,
    NodeGeneralInfo,
    NodeSensorInfo,
    NodeVentilationInfo,
)
import pytest

from homeassistant.components.duco.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_HOST = "192.168.1.100"
TEST_MAC = "aa:bb:cc:dd:ee:ff"

USER_INPUT = {CONF_HOST: TEST_HOST}


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
    return [
        Node(
            node_id=1,
            general=NodeGeneralInfo(
                node_type="BOX",
                sub_type=1,
                network_type="VIRT",
                parent=0,
                asso=0,
                name="Living",
                identify=0,
            ),
            ventilation=NodeVentilationInfo(
                state="AUTO",
                time_state_remain=0,
                time_state_end=0,
                mode="AUTO",
                flow_lvl_tgt=0,
            ),
            sensor=NodeSensorInfo(
                co2=None,
                iaq_co2=None,
                rh=None,
                iaq_rh=None,
            ),
        ),
        Node(
            node_id=2,
            general=NodeGeneralInfo(
                node_type="UCCO2",
                sub_type=0,
                network_type="RF",
                parent=1,
                asso=1,
                name="Office CO2",
                identify=0,
            ),
            ventilation=NodeVentilationInfo(
                state="AUTO",
                time_state_remain=0,
                time_state_end=0,
                mode="-",
                flow_lvl_tgt=None,
            ),
            sensor=NodeSensorInfo(
                co2=405,
                iaq_co2=80,
                rh=None,
                iaq_rh=None,
            ),
        ),
        Node(
            node_id=113,
            general=NodeGeneralInfo(
                node_type="BSRH",
                sub_type=0,
                network_type="RF",
                parent=1,
                asso=1,
                name="Bathroom RH",
                identify=0,
            ),
            ventilation=NodeVentilationInfo(
                state="AUTO",
                time_state_remain=0,
                time_state_end=0,
                mode="-",
                flow_lvl_tgt=None,
            ),
            sensor=NodeSensorInfo(
                co2=None,
                iaq_co2=None,
                rh=42.0,
                iaq_rh=85,
            ),
        ),
        Node(
            node_id=50,
            general=NodeGeneralInfo(
                node_type="UCRH",
                sub_type=0,
                network_type="RF",
                parent=1,
                asso=1,
                name="Kitchen RH",
                identify=0,
            ),
            ventilation=NodeVentilationInfo(
                state="AUTO",
                time_state_remain=0,
                time_state_end=0,
                mode="-",
                flow_lvl_tgt=None,
            ),
            sensor=NodeSensorInfo(
                co2=None,
                iaq_co2=None,
                rh=61.0,
                iaq_rh=90,
            ),
        ),
    ]


@pytest.fixture
def mock_duco_client(
    mock_board_info: BoardInfo,
    mock_lan_info: LanInfo,
    mock_nodes: list[Node],
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
        client.async_get_board_info.return_value = mock_board_info
        client.async_get_lan_info.return_value = mock_lan_info
        client.async_get_nodes.return_value = mock_nodes
        client.async_get_diagnostics.return_value = [
            DiagComponent(component="Ventilation", status=DiagStatus.OK)
        ]
        client.async_get_write_req_remaining.return_value = 100
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
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
