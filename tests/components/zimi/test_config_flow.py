"""Tests for the zimi config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from zcc import ControlPoint, ControlPointDescription, ControlPointError

from homeassistant import config_entries
from homeassistant.components.zimi.config_flow import ZimiConfigErrors
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
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


async def test_user_discovery_success(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test user form transitions to creation if zcc discovery succeeds."""

    discovery_mock.discover.return_value = ControlPointDescription(
        host=INPUT_HOST, port=INPUT_PORT
    )

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


async def test_user_discovery_failure(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
) -> None:
    """Test user form transitions to finish step if zcc discovery fails."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "finish"


async def test_finish_manual_success(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test finish form transitions to creation with valid data."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ZIMI Controller ({INPUT_HOST}:{INPUT_PORT})"
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


async def test_finish_manual_cannot_connect(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test finish form transitions via cannot_connect to creation."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    # First attempt fails with ControlPointError when attempting to connect
    api_mock.side_effect = ControlPointError("Connection failed")

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": ZimiConfigErrors.CANNOT_CONNECT}

    # Second attempt succeeds
    api_mock.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ZIMI Controller ({INPUT_HOST}:{INPUT_PORT})"
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


async def test_finish_manual_gethostbyname_error(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
) -> None:
    """Test finish form transitions via gethostbyname failure to creation."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    # First attempt fails with name lookup failure
    socket_mock.gethostbyname.return_value = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": ZimiConfigErrors.INVALID_HOST}

    # Second attempt succeeds
    api_mock.side_effect = None
    socket_mock.gethostbyname.return_value = "xxx"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ZIMI Controller ({INPUT_HOST}:{INPUT_PORT})"
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


@pytest.mark.parametrize(
    ("side_effect", "error_expected"),
    [
        (ConnectionRefusedError, {"base": ZimiConfigErrors.CONNECTION_REFUSED}),
        (TimeoutError, {"base": ZimiConfigErrors.TIMEOUT}),
    ],
)
async def test_finish_manual_socket_errors(
    hass: HomeAssistant,
    api_mock: MagicMock,
    discovery_mock: MagicMock,
    socket_mock: MagicMock,
    side_effect: Exception,
    error_expected: dict,
) -> None:
    """Test finish form transitions via socket errors to creation."""

    discovery_mock.discover.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    api_mock.return_value.mac = INPUT_MAC
    api_mock.return_value.ready = True

    # First attempt fails with socket errors
    socket_mock.socket.return_value.connect.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == error_expected

    # Second attempt succeeds
    discovery_mock.reset_mock(return_value=True, side_effect=True)
    socket_mock.reset_mock(return_value=True, side_effect=True)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"ZIMI Controller ({INPUT_HOST}:{INPUT_PORT})"
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }
