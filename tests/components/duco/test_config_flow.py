"""Tests for the Duco config flow."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import LanInfo
import pytest

from homeassistant.components.duco.const import DOMAIN
from homeassistant.config_entries import SOURCE_DHCP, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import TEST_HOST, TEST_MAC, USER_INPUT

from tests.common import MockConfigEntry

ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=IPv4Address(TEST_HOST),
    ip_addresses=[IPv4Address(TEST_HOST)],
    port=80,
    hostname="duco_061293.local.",
    type="_http._tcp.local.",
    name="DUCO [a0dd6c061293]._http._tcp.local.",
    properties={},
)

DHCP_DISCOVERY = DhcpServiceInfo(
    ip=TEST_HOST,
    hostname="duco_ddeeff",
    macaddress="aabbccddeeff",
)


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test a successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SILENT_CONNECT"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_MAC


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (DucoConnectionError("Connection refused"), "cannot_connect"),
        (DucoError("Unexpected error"), "unknown"),
    ],
)
async def test_user_flow_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test handling of connection and unknown errors in the user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_duco_client.async_get_board_info.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}

    mock_duco_client.async_get_board_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate config entry is aborted."""
    mock_config_entry.add_to_hass(hass)

    # Second attempt for the same device
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery_new_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test zeroconf discovery of a new device shows confirmation form and creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SILENT_CONNECT"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_MAC


async def test_zeroconf_discovery_updates_host(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf discovery updates the host of an existing entry."""
    mock_config_entry.add_to_hass(hass)

    new_ip = "192.168.1.200"
    discovery = ZeroconfServiceInfo(
        ip_address=IPv4Address(new_ip),
        ip_addresses=[IPv4Address(new_ip)],
        port=80,
        hostname="duco_061293.local.",
        type="_http._tcp.local.",
        name="DUCO [a0dd6c061293]._http._tcp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_ip


async def test_zeroconf_discovery_already_configured_same_ip(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf discovery with unchanged IP aborts as already_configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (DucoConnectionError("Connection refused"), "cannot_connect"),
        (DucoError("Unexpected error"), "unknown"),
    ],
)
async def test_zeroconf_discovery_exceptions(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    expected_reason: str,
) -> None:
    """Test zeroconf discovery aborts on connection and unknown errors."""
    mock_duco_client.async_get_board_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_success(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a successful reconfigure flow updates host and reloads."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    mock_duco_client.async_get_board_info.side_effect = DucoConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.50"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_duco_client.async_get_board_info.side_effect = None
    new_host = "192.168.1.200"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfigure_flow_wrong_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reconfigure flow aborts when pointing to a different device."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    # Simulate a different MAC returned by the new host
    different_mac = "11:22:33:44:55:66"
    mock_duco_client.async_get_lan_info.return_value = LanInfo(
        mode="WIFI_CLIENT",
        ip="192.168.1.200",
        net_mask="255.255.255.0",
        default_gateway="192.168.1.1",
        dns="8.8.8.8",
        mac=different_mac,
        host_name="duco-other",
        rssi_wifi=-60,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (DucoConnectionError("Connection refused"), "cannot_connect"),
        (DucoError("Unexpected error"), "unknown"),
    ],
)
async def test_reconfigure_flow_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure flow shows error on connection failure."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)

    mock_duco_client.async_get_board_info.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    assert result["errors"] == {"base": expected_error}

    mock_duco_client.async_get_board_info.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.200"}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


async def test_dhcp_discovery_new_device(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test DHCP discovery of a new device shows confirmation form and creates entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {"name": "SILENT_CONNECT"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "SILENT_CONNECT"
    assert result["data"] == USER_INPUT
    assert result["result"].unique_id == TEST_MAC


async def test_dhcp_discovery_updates_host(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery updates the host of an existing entry."""
    mock_config_entry.add_to_hass(hass)

    new_ip = "192.168.1.200"
    discovery = DhcpServiceInfo(
        ip=new_ip,
        hostname="duco_ddeeff",
        macaddress="aabbccddeeff",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == new_ip


async def test_dhcp_discovery_already_configured_same_ip(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery with unchanged IP aborts as already_configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (DucoConnectionError("Connection refused"), "cannot_connect"),
        (DucoError("Unexpected error"), "unknown"),
    ],
)
async def test_dhcp_discovery_exceptions(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    expected_reason: str,
) -> None:
    """Test DHCP discovery aborts on connection and unknown errors."""
    mock_duco_client.async_get_board_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_dhcp_discovery_exception_recovery(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test DHCP discovery recovers after an initial exception and creates the entry."""
    mock_duco_client.async_get_board_info.side_effect = DucoConnectionError(
        "Connection refused"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"

    mock_duco_client.async_get_board_info.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_DHCP},
        data=DHCP_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == TEST_MAC
