"""Tests for Wibeee config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import aiohttp

from homeassistant import config_entries
from homeassistant.components.wibeee.const import DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.dhcp import DhcpServiceInfo

from .conftest import MOCK_HOST, MOCK_MAC

from tests.common import MockConfigEntry


async def test_user_step_shows_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test that the user step shows a form with host input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_user_step_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: MagicMock,
) -> None:
    """Test user step validates device and creates the entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["result"].unique_id == MOCK_MAC


async def test_user_step_connection_error(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: MagicMock,
) -> None:
    """Test user step handles connection error."""
    # validate_input calls async_fetch_device_info
    mock_wibeee_api_config_flow.async_fetch_device_info.side_effect = TimeoutError(
        "error"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert "errors" in result
    assert result["errors"][CONF_HOST] == "no_device_info"


async def test_user_step_invalid_device(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: MagicMock,
) -> None:
    """Test user step handles non-Wibeee device (no device info)."""
    mock_wibeee_api_config_flow.async_fetch_device_info.return_value = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"][CONF_HOST] == "no_device_info"


async def test_dhcp_discovery(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_wibeee_api_config_flow: MagicMock,
) -> None:
    """Test DHCP discovery flow creates an entry."""
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST


# -- DHCP and exception-path tests --


async def test_dhcp_already_configured_updates_host(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test DHCP discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = DhcpServiceInfo(
        ip="192.168.1.250",
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.250"


async def test_dhcp_not_wibeee_device(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test DHCP discovery aborts when device is not a Wibeee."""
    mock_wibeee_api.async_check_connection.return_value = False
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="not_wibeee",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_wibeee_device"


async def test_dhcp_connection_error(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test DHCP discovery aborts when connection fails."""
    mock_wibeee_api.async_check_connection.side_effect = aiohttp.ClientError("boom")
    discovery_info = DhcpServiceInfo(
        ip=MOCK_HOST,
        macaddress=MOCK_MAC,
        hostname="wibeee_test",
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_DHCP},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_wibeee_device"


async def test_user_step_already_configured(
    hass: HomeAssistant,
    mock_wibeee_api: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test user step aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_step_unexpected_exception(
    hass: HomeAssistant, mock_wibeee_api: MagicMock
) -> None:
    """Test user step shows generic error on unexpected exception."""
    mock_wibeee_api.async_fetch_device_info.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "unknown"
