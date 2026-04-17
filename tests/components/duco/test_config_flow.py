"""Tests for the Duco config flow."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError, DucoError
from duco.models import LanInfo
import pytest

from homeassistant.components.duco.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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
        context={"source": "zeroconf"},
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
        context={"source": "zeroconf"},
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
        context={"source": "zeroconf"},
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
async def test_zeroconf_discovery_connection_error(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    exception: Exception,
    expected_reason: str,
) -> None:
    """Test zeroconf discovery aborts on connection and unknown errors."""
    mock_duco_client.async_get_board_info.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


@pytest.mark.parametrize(
    "invalid_name",
    [
        "ducotje._http._tcp.local.",
        "DUCO Box._http._tcp.local.",
        "something_duco._http._tcp.local.",
        "DUCO [invalid]._http._tcp.local.",
        "DUCO [a0dd6c06129]._http._tcp.local.",  # Wrong MAC length
        "My Duco Device._http._tcp.local.",
    ],
)
async def test_zeroconf_discovery_rejects_invalid_names(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    invalid_name: str,
) -> None:
    """Test zeroconf discovery rejects devices that don't match Duco naming pattern."""
    invalid_discovery = ZeroconfServiceInfo(
        ip_address=IPv4Address(TEST_HOST),
        ip_addresses=[IPv4Address(TEST_HOST)],
        port=80,
        hostname="device.local.",
        type="_http._tcp.local.",
        name=invalid_name,
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=invalid_discovery,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_duco_device"


@pytest.mark.parametrize(
    "valid_name",
    [
        "DUCO [a0dd6c061293]._http._tcp.local.",
        "duco [123abc456def]._http._tcp.local.",  # Lowercase should work with IGNORECASE
        "DUCO [ABCDEF123456]._http._tcp.local.",  # Uppercase hex
    ],
)
async def test_zeroconf_discovery_accepts_valid_names(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    valid_name: str,
) -> None:
    """Test zeroconf discovery accepts valid Duco device names."""
    valid_discovery = ZeroconfServiceInfo(
        ip_address=IPv4Address(TEST_HOST),
        ip_addresses=[IPv4Address(TEST_HOST)],
        port=80,
        hostname="duco.local.",
        type="_http._tcp.local.",
        name=valid_name,
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=valid_discovery,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"


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

    new_host = "192.168.1.200"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: new_host}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_HOST] == new_host


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
    assert result["reason"] == "wrong_device"


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
