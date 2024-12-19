"""Tests for the zimi config flow."""

import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zcc import ControlPointError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac


@pytest.fixture(name="discovery_service")
def mock_discovery_service():
    """Mock the ControlPointDiscoveryService."""
    with patch(
        "homeassistant.components.zimi.config_flow.ControlPointDiscoveryService"
    ) as service:
        discovery = MagicMock()
        discovery.discover = AsyncMock()
        service.return_value = discovery
        yield discovery


@pytest.fixture(name="socket_mock")
def mock_socket():
    """Mock socket operations."""
    with patch("homeassistant.components.zimi.config_flow.socket") as mock:
        mock.gethostbyname = MagicMock()
        mock.socket = MagicMock()
        mock.AF_INET = socket.AF_INET
        mock.SOCK_STREAM = socket.SOCK_STREAM
        yield mock


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_successful_config_manual(
    hass: HomeAssistant, socket_mock: MagicMock
) -> None:
    """Test successful configuration with manual host entry."""
    test_mac = "AA:BB:CC:DD:EE:FF"
    test_host = "192.168.1.100"
    test_port = 5003

    socket_mock.gethostbyname.return_value = test_host
    socket_mock.socket.return_value.connect = MagicMock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: test_host,
            CONF_PORT: test_port,
            CONF_MAC: test_mac,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZIMI Controller"
    assert result["data"] == {
        "title": "ZIMI Controller",
        "host": test_host,
        "port": test_port,
        "timeout": 3,
        "verbosity": 1,
        "watchdog": 1800,
        "mac": format_mac(test_mac),
    }


async def test_successful_config_discovery(
    hass: HomeAssistant, discovery_service
) -> None:
    """Test successful configuration with automatic discovery."""
    test_mac = "AA:BB:CC:DD:EE:FF"
    discovered_host = "192.168.1.200"
    discovered_port = 5003

    discovery_description = MagicMock()
    discovery_description.host = discovered_host
    discovery_description.port = discovered_port
    discovery_service.discover.return_value = discovery_description

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",  # Empty host triggers discovery
            CONF_PORT: 5003,
            CONF_MAC: test_mac,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == discovered_host
    assert result["data"]["port"] == discovered_port


async def test_discovery_failure(hass: HomeAssistant, discovery_service) -> None:
    """Test failed discovery."""
    discovery_service.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",
            CONF_PORT: 5003,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_failure"}


async def test_invalid_host(hass: HomeAssistant, socket_mock) -> None:
    """Test error on invalid host."""
    socket_mock.gethostbyname.side_effect = socket.herror

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "invalid_host",
            CONF_PORT: 5003,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_connection_refused(hass: HomeAssistant, socket_mock) -> None:
    """Test error on connection refused."""
    socket_mock.gethostbyname.return_value = "192.168.1.100"
    socket_mock.socket.return_value.connect.side_effect = ConnectionRefusedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 5003,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "connection_refused"}


async def test_connection_timeout(hass: HomeAssistant, socket_mock) -> None:
    """Test error on connection timeout."""
    socket_mock.gethostbyname.return_value = "192.168.1.100"
    socket_mock.socket.return_value.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 5003,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "timeout"}


async def test_unexpected_error(hass: HomeAssistant, socket_mock) -> None:
    """Test handling of unexpected errors."""
    socket_mock.gethostbyname.return_value = "192.168.1.100"
    socket_mock.socket.return_value.connect.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 5003,
            CONF_MAC: "AA:BB:CC:DD:EE:FF",
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
