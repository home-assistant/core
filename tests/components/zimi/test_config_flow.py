"""Tests for the zimi config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import format_mac

MOCK_MAC = "aa:bb:cc:dd:ee:ff"
MOCK_HOST = "192.168.1.100"
MOCK_PORT = 5003


@pytest.fixture
def api_mock():
    """Mock aysnc_connect_to_controller to return api instance."""
    with patch(
        "homeassistant.components.zimi.config_flow.async_connect_to_controller",
    ) as mock:
        api = MagicMock(spec=ControlPoint)
        api.mac = MOCK_MAC
        api.ready = True
        mock.return_value = api
        yield mock


@pytest.fixture
def discovery_mock():
    """Mock the ControlPointDiscoveryService."""
    with patch(
        "homeassistant.components.zimi.config_flow.ControlPointDiscoveryService",
        autospec=True,
    ) as mock:
        discovery = MagicMock()
        discovery.discover = AsyncMock()
        mock.return_value = discovery
        yield discovery


@pytest.fixture
def socket_mock():
    """Mock socket operations."""
    with patch(
        "homeassistant.components.zimi.config_flow.socket", autospec=True
    ) as mock:
        mock.gethostbyname.return_value = MOCK_HOST
        yield mock


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_successful_config_manual(
    hass: HomeAssistant,
    api_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test successful configuration with manual host entry."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZIMI Controller"
    assert result["data"] == {
        "host": MOCK_HOST,
        "port": MOCK_PORT,
        "mac": format_mac(MOCK_MAC),
    }


async def test_successful_config_discovery(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test successful configuration with automatic discovery."""

    discovery_mock.discover.return_value = ControlPointDescription(
        host=MOCK_HOST, port=MOCK_PORT
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",  # Empty host triggers discovery
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == MOCK_HOST
    assert result["data"]["port"] == MOCK_PORT


async def test_discovery_failure(hass: HomeAssistant, discovery_mock) -> None:
    """Test failed discovery."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_failure"}


async def test_invalid_host(
    hass: HomeAssistant, socket_mock: MagicMock | AsyncMock
) -> None:
    """Test error on invalid host."""
    socket_mock.gethostbyname.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


async def test_connection_refused(
    hass: HomeAssistant, socket_mock: MagicMock | AsyncMock
) -> None:
    """Test error on connection refused."""
    socket_mock.socket.return_value.connect.side_effect = ConnectionRefusedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "connection_refused"}


async def test_connection_timeout(
    hass: HomeAssistant, socket_mock: MagicMock | AsyncMock
) -> None:
    """Test error on connection timeout."""
    socket_mock.socket.return_value.connect.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "timeout"}


async def test_unexpected_error(
    hass: HomeAssistant, socket_mock: MagicMock | AsyncMock
) -> None:
    """Test handling of unexpected errors."""
    socket_mock.socket.return_value.connect.side_effect = Exception("Unexpected error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
            CONF_PORT: MOCK_PORT,
            CONF_MAC: MOCK_MAC,
        },
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
