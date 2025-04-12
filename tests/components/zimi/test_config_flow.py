"""Tests for the zimi config flow."""

from unittest.mock import MagicMock, patch

import pytest
from zcc import (
    ControlPointCannotConnectError,
    ControlPointConnectionRefusedError,
    ControlPointDescription,
    ControlPointError,
    ControlPointInvalidHostError,
    ControlPointTimeoutError,
)

from homeassistant import config_entries
from homeassistant.components.zimi.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import format_mac

INPUT_MAC = "aa:bb:cc:dd:ee:ff"
INPUT_MAC_EXTRA = "aa:bb:cc:dd:ee:ee"
INPUT_HOST = "192.168.1.100"
INPUT_HOST_EXTRA = "192.168.1.101"
INPUT_PORT = 5003
INPUT_PORT_EXTRA = 5004

INVALID_INPUT_MAC = "xyz"
MISMATCHED_INPUT_MAC = "aa:bb:cc:dd:ee:ee"
SELECTED_HOST_AND_PORT = "selected_host_and_port"


@pytest.fixture
def discovery_mock():
    """Mock the ControlPointDiscoveryService."""
    with patch(
        "homeassistant.components.zimi.config_flow.ControlPointDiscoveryService",
        autospec=True,
    ) as mock:
        mock.return_value = mock
        yield mock


async def test_user_discovery_success(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
) -> None:
    """Test user form transitions to creation if zcc discovery succeeds."""

    discovery_mock.discovers.return_value = [
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT)
    ]

    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT, mac=INPUT_MAC)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "host": INPUT_HOST,
        "port": INPUT_PORT,
        "mac": format_mac(INPUT_MAC),
    }


async def test_user_discovery_success_selection(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
) -> None:
    """Test user form transitions via selection to creation if zcc discovery succeeds has multiple hosts."""

    discovery_mock.discovers.return_value = [
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT),
        ControlPointDescription(host=INPUT_HOST_EXTRA, port=INPUT_PORT_EXTRA),
    ]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(
            host=INPUT_HOST_EXTRA, port=INPUT_PORT_EXTRA, mac=INPUT_MAC_EXTRA
        )
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            SELECTED_HOST_AND_PORT: INPUT_HOST_EXTRA + ":" + str(INPUT_PORT_EXTRA),
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        "host": INPUT_HOST_EXTRA,
        "port": INPUT_PORT_EXTRA,
        "mac": format_mac(INPUT_MAC_EXTRA),
    }


async def test_user_discovery_failure(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
) -> None:
    """Test user form transitions to finish step if zcc discovery fails."""

    discovery_mock.discovers.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    assert result["step_id"] == "manual"


async def test_finish_manual_success(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
) -> None:
    """Test finish form transitions to creation with valid data."""

    discovery_mock.discovers.side_effect = ControlPointError("Discovery failed")
    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT, mac=INPUT_MAC)
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

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
    discovery_mock: MagicMock,
) -> None:
    """Test finish form transitions via cannot_connect to creation."""

    discovery_mock.discovers.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt fails with CANNOT_CONNECT when attempting to connect
    discovery_mock.return_value.validate_connection.side_effect = (
        ControlPointCannotConnectError
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt succeeds
    discovery_mock.return_value.validate_connection.side_effect = None
    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT, mac=INPUT_MAC)
    )

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
    discovery_mock: MagicMock,
) -> None:
    """Test finish form transitions via gethostbyname failure to creation."""

    discovery_mock.discovers.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt fails with name lookup failure when attempting to connect
    discovery_mock.return_value.validate_connection.side_effect = (
        ControlPointInvalidHostError
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: INPUT_HOST,
            CONF_PORT: INPUT_PORT,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_host"}

    # Second attempt succeeds
    discovery_mock.return_value.validate_connection.side_effect = None
    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT, mac=INPUT_MAC)
    )

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
        (
            ControlPointConnectionRefusedError,
            {"base": "connection_refused"},
        ),
        (
            ControlPointTimeoutError,
            {"base": "timeout"},
        ),
    ],
)
async def test_finish_manual_socket_errors(
    hass: HomeAssistant,
    discovery_mock: MagicMock,
    side_effect: Exception,
    error_expected: dict,
) -> None:
    """Test finish form transitions via socket errors to creation."""

    discovery_mock.discovers.side_effect = ControlPointError("Discovery failed")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First attempt fails with socket errors
    discovery_mock.return_value.validate_connection.side_effect = side_effect

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
    discovery_mock.return_value.validate_connection.side_effect = None
    discovery_mock.return_value.validate_connection.return_value = (
        ControlPointDescription(host=INPUT_HOST, port=INPUT_PORT, mac=INPUT_MAC)
    )

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
