"""Tests for ADAM Audio config flow."""

from __future__ import annotations

from ipaddress import IPv4Address
from unittest.mock import MagicMock

from homeassistant import config_entries
from homeassistant.components.adam_audio.const import (
    CONF_DESCRIPTION,
    CONF_DEVICE_NAME,
    CONF_HOST,
    CONF_PORT,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import (
    MOCK_DESCRIPTION,
    MOCK_DEVICE_NAME,
    MOCK_HOST,
    MOCK_PORT,
    MOCK_SERIAL,
)


async def test_user_flow_success(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test the manual user flow with a successful connection."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DESCRIPTION
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_user_flow_connection_error(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test the manual user flow when connection fails."""
    mock_client.async_setup.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_zeroconf_flow_empty_hostname(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test zeroconf when hostname is empty (falls back to IP-based device_id)."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=MOCK_PORT,
        hostname="",
        type="_oca._udp.local.",
        name="._oca._udp.local.",
        properties={},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == MOCK_HOST


async def test_zeroconf_flow_success(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test zeroconf discovery with a successful connection."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=MOCK_PORT,
        hostname="ASeries-41472b.local.",
        type="_oca._udp.local.",
        name="ASeries-41472b._oca._udp.local.",
        properties={},
    )

    # Step 1: zeroconf triggers discovery → shows confirm form
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Step 2: user confirms → entry created
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DESCRIPTION
    assert result["data"][CONF_HOST] == MOCK_HOST
    assert result["data"][CONF_PORT] == MOCK_PORT
    assert result["data"][CONF_DEVICE_NAME] == MOCK_DEVICE_NAME
    assert result["data"][CONF_SERIAL] == MOCK_SERIAL


async def test_zeroconf_flow_connection_failure(
    hass: HomeAssistant, mock_client: MagicMock
) -> None:
    """Test zeroconf discovery when connection fails (uses fallback metadata)."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=IPv4Address(MOCK_HOST),
        ip_addresses=[IPv4Address(MOCK_HOST)],
        port=MOCK_PORT,
        hostname="ASeries-41472b.local.",
        type="_oca._udp.local.",
        name="ASeries-41472b._oca._udp.local.",
        properties={},
    )

    mock_client.async_setup.return_value = False

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    # Confirm with fallback data
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    # Falls back to device_id derived from hostname
    assert result["data"][CONF_DEVICE_NAME] == "ASeries-41472b"
    assert result["data"][CONF_DESCRIPTION] == "ASeries-41472b"


async def test_user_flow_exception(hass: HomeAssistant, mock_client: MagicMock) -> None:
    """Test _async_try_connect returns None when an unexpected exception occurs."""
    mock_client.async_setup.side_effect = RuntimeError("boom")

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST, CONF_PORT: MOCK_PORT},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
