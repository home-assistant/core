"""Config flow tests for the Unraid integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from unraid_api.exceptions import (
    UnraidAuthenticationError,
    UnraidConnectionError,
    UnraidSSLError,
)

from homeassistant import config_entries
from homeassistant.components.unraid.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST, CONF_PORT, CONF_SSL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import create_mock_server_info

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_unraid_client")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "tower"
    assert result["data"] == {
        CONF_HOST: "unraid.local",
        CONF_PORT: 80,
        CONF_API_KEY: "valid-api-key",
        CONF_SSL: True,
    }


@pytest.mark.usefixtures("mock_unraid_client")
async def test_user_flow_with_custom_port(hass: HomeAssistant) -> None:
    """Test user flow with custom port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "unraid.local",
            CONF_PORT: 8443,
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PORT] == 8443
    assert result["data"][CONF_SSL] is True


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (UnraidAuthenticationError("Invalid API key"), {CONF_API_KEY: "invalid_auth"}),
        (UnraidConnectionError("Connection refused"), {"base": "cannot_connect"}),
        (RuntimeError("Unexpected"), {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_unraid_client: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test error handling in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Configure mock to return error
    mock_unraid_client.test_connection.side_effect = side_effect

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "test-key",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    # Test recovery after error - reset mock to succeed
    mock_unraid_client.test_connection.side_effect = None
    mock_unraid_client.test_connection.return_value = True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_ssl_fallback_to_http(
    hass: HomeAssistant, mock_unraid_client: MagicMock
) -> None:
    """Test automatic fallback from HTTPS to HTTP on SSL error."""
    call_count = 0
    original_test_connection = mock_unraid_client.test_connection

    async def mock_test_connection(*args, **kwargs):
        """Return different result based on call count (simulating SSL then HTTP)."""
        nonlocal call_count
        call_count += 1
        # First call is HTTPS (fails), second call is HTTP (succeeds)
        if call_count == 1:
            raise UnraidSSLError("SSL certificate verify failed")
        return await original_test_connection(*args, **kwargs)

    mock_unraid_client.test_connection = AsyncMock(side_effect=mock_test_connection)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "test-key",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SSL] is False
    assert call_count == 2


async def test_user_flow_unsupported_version_aborts(
    hass: HomeAssistant, mock_unraid_client: MagicMock
) -> None:
    """Test old Unraid version aborts the flow."""
    mock_unraid_client.get_version.return_value = {"unraid": "6.9.0", "api": "4.10.0"}

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "valid-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported_version"


async def test_user_flow_cannot_get_version_aborts(
    hass: HomeAssistant, mock_unraid_client: MagicMock
) -> None:
    """Test inability to get version aborts the flow."""
    mock_unraid_client.get_version.side_effect = RuntimeError("API error")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "valid-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_get_version"


async def test_user_flow_no_server_uuid_aborts(
    hass: HomeAssistant, mock_unraid_client: MagicMock
) -> None:
    """Test missing server UUID aborts the flow."""
    mock_unraid_client.get_server_info.return_value = create_mock_server_info(
        uuid=None, hostname="tower"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "unraid.local",
            CONF_API_KEY: "valid-api-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_server_uuid"


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_unraid_client: MagicMock,
) -> None:
    """Test duplicate server UUID is rejected."""
    mock_config_entry.add_to_hass(hass)

    mock_unraid_client.get_server_info.return_value = create_mock_server_info(
        uuid="test-uuid-1234"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "192.168.1.200",
            CONF_API_KEY: "another-key",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
