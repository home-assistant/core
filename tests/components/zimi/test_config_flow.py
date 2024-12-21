"""Tests for the zimi config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import format_mac

INPUT_MAC = "aa:bb:cc:dd:ee:ff"
INPUT_HOST = "192.168.1.100"
INPUT_PORT = 5003

INVALID_INPUT_MAC = "xyz"
MISMATCHED_INPUT_MAC = "aa:bb:cc:dd:ee:ee"


@pytest.fixture
def api_mock():
    """Mock aysnc_connect_to_controller to return api instance."""
    with patch(
        "homeassistant.components.zimi.config_flow.async_connect_to_controller",
    ) as mock:
        api = MagicMock(spec=ControlPoint)
        mock.return_value = api
        yield mock


@pytest.fixture
def discovery_mock():
    """Mock the ControlPointDiscoveryService."""
    with patch(
        "homeassistant.components.zimi.config_flow.ControlPointDiscoveryService",
        autospec=True,
    ) as mock:
        mock.discover = AsyncMock()
        mock.return_value = mock
        yield mock


@pytest.fixture
def socket_mock():
    """Mock socket operations."""
    with patch(
        "homeassistant.components.zimi.config_flow.socket", autospec=True
    ) as mock:
        yield mock


async def test_user_form(hass: HomeAssistant) -> None:
    """Test we get the user form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_config_success(
    hass: HomeAssistant,
    api_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test successful configuration with manual host entry."""

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "ZIMI Controller"
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


async def test_discovery_success(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test successful configuration with automatic discovery."""

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    discovery_mock.discover.return_value = ControlPointDescription(
        host=INPUT_HOST, port=INPUT_PORT
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",  # Empty host triggers discovery
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"]["host"] == INPUT_HOST
    assert result["data"]["port"] == INPUT_PORT


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
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "discovery_failure"}


async def test_api_failure(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test api failure."""

    api_mock.side_effect = ConfigEntryNotReady

    discovery_mock.discover.return_value = ControlPointDescription(
        host=INPUT_HOST, port=INPUT_PORT
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "",  # Empty host triggers discovery
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_gethostbyname_failure(
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
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}


@pytest.mark.parametrize(
    ("input_mac", "error_expected"),
    [
        (MISMATCHED_INPUT_MAC, {"base": "mismatched_mac"}),
        (INVALID_INPUT_MAC, {"base": "invalid_mac"}),
    ],
)
async def test_mac_failures(
    hass: HomeAssistant,
    api_mock: MagicMock,
    socket_mock: MagicMock,
    input_mac: str,
    error_expected: dict,
) -> None:
    """Test mac configuration failures."""

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
            CONF_MAC: input_mac,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == error_expected


@pytest.mark.parametrize(
    ("side_effect", "error_expected"),
    [
        (ConnectionRefusedError, {"base": "connection_refused"}),
        (TimeoutError, {"base": "timeout"}),
        (Exception("Unexpected error"), {"base": "unknown"}),
    ],
)
async def test_socket_exceptions(
    hass: HomeAssistant,
    socket_mock: MagicMock,
    side_effect: Exception,
    error_expected: dict,
) -> None:
    """Test socket exception handling."""
    socket_mock.socket.return_value.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
            CONF_MAC: INPUT_MAC,
        },
    )

    assert result["type"] is data_entry_flow.FlowResultType.FORM
    assert result["errors"] == error_expected
