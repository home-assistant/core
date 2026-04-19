"""Tests for the WattWächter Plus config flow."""

from __future__ import annotations

from ipaddress import ip_address
from unittest.mock import AsyncMock

from aio_wattwaechter import (
    WattwaechterAuthenticationError,
    WattwaechterConnectionError,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.wattwaechter.const import (
    CONF_DEVICE_ID,
    CONF_DEVICE_NAME,
    CONF_FW_VERSION,
    CONF_MAC,
    CONF_MODEL,
    DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .conftest import (
    MOCK_DEVICE_ID,
    MOCK_DEVICE_NAME,
    MOCK_FW_VERSION,
    MOCK_HOST,
    MOCK_MAC,
    MOCK_MODEL,
    MOCK_SYSTEM_INFO,
    MOCK_TOKEN,
)

from tests.common import MockConfigEntry

MOCK_ZEROCONF_DISCOVERY = ZeroconfServiceInfo(
    ip_address=ip_address(MOCK_HOST),
    ip_addresses=[ip_address(MOCK_HOST)],
    hostname="wattwaechter.local.",
    port=80,
    type="_wattwaechter._tcp.local.",
    name=f"WWP-{MOCK_DEVICE_ID}._wattwaechter._tcp.local.",
    properties={
        "id": f"WWP-{MOCK_DEVICE_ID}",
        "model": MOCK_MODEL,
        "ver": MOCK_FW_VERSION,
        "mac": MOCK_MAC,
    },
)


# --- User Flow ---


async def test_user_flow_success(hass: HomeAssistant, mock_client: AsyncMock) -> None:
    """Test successful manual configuration without auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
        CONF_MODEL: "WW-Plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }


async def test_user_flow_auth_required(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test user flow redirects to auth step when device requires a token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # system_info raises auth error → redirect to auth step
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    # Submit token → success
    mock_client.system_info.side_effect = None
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: MOCK_TOKEN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
        CONF_MODEL: "WW-Plus",
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test user flow shows error on connection failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_client.system_info.side_effect = WattwaechterConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "cannot_connect"


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts when device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# --- Auth Step Errors (parametrized) ---


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (WattwaechterAuthenticationError("Invalid token"), "invalid_auth"),
        (WattwaechterConnectionError("Connection lost"), "cannot_connect"),
    ],
)
async def test_auth_step_errors(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test auth step shows errors for invalid token and connection failure."""
    # Trigger auth step via user flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: MOCK_HOST},
    )
    assert result["step_id"] == "auth"

    # Submit token with error
    mock_client.system_info.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: "bad-token"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"]["base"] == expected_error


# --- Zeroconf Flow ---


async def test_zeroconf_flow_no_token_needed(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test zeroconf discovery when device doesn't require a token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
        CONF_MODEL: MOCK_MODEL,
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }


async def test_zeroconf_flow_token_required(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test zeroconf discovery when device requires a token."""
    mock_client.system_info.side_effect = WattwaechterAuthenticationError(
        "Auth required"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    # Submit token → success
    mock_client.system_info.side_effect = None
    mock_client.system_info.return_value = MOCK_SYSTEM_INFO
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_TOKEN: MOCK_TOKEN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DEVICE_NAME
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: MOCK_TOKEN,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_NAME: MOCK_DEVICE_NAME,
        CONF_MODEL: MOCK_MODEL,
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }


async def test_zeroconf_flow_cannot_connect(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test zeroconf aborts when device is unreachable."""
    mock_client.system_info.side_effect = WattwaechterConnectionError(
        "Connection refused"
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_zeroconf_flow_already_configured(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf aborts when device is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_flow_device_name_fetch_fails(
    hass: HomeAssistant, mock_client: AsyncMock
) -> None:
    """Test zeroconf uses fallback title when device_name fetch fails."""
    mock_client.settings.side_effect = WattwaechterConnectionError("Connection lost")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=MOCK_ZEROCONF_DISCOVERY,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "zeroconf_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"WattWächter {MOCK_DEVICE_ID}"
    assert result["result"].unique_id == MOCK_DEVICE_ID
    assert result["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_TOKEN: None,
        CONF_DEVICE_ID: MOCK_DEVICE_ID,
        CONF_DEVICE_NAME: None,
        CONF_MODEL: MOCK_MODEL,
        CONF_FW_VERSION: MOCK_FW_VERSION,
        CONF_MAC: MOCK_MAC,
    }
