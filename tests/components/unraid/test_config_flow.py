"""Config flow tests for the Unraid integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

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

from .conftest import create_mock_server_info, create_mock_unraid_client

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user_flow(
    hass: HomeAssistant, mock_unraid_client_config_flow: MagicMock
) -> None:
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


async def test_user_flow_with_custom_port(
    hass: HomeAssistant, mock_unraid_client_config_flow: MagicMock
) -> None:
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
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test error handling in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_api = MagicMock()
        mock_api.test_connection = AsyncMock(side_effect=side_effect)
        mock_api.close = AsyncMock()
        mock_client.return_value = mock_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "unraid.local",
                CONF_API_KEY: "test-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == expected_error

    # Test recovery after error
    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_client.return_value = create_mock_unraid_client(create_mock_server_info())

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_HOST: "unraid.local",
                CONF_API_KEY: "valid-api-key",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_ssl_fallback_to_http(hass: HomeAssistant) -> None:
    """Test automatic fallback from HTTPS to HTTP on SSL error."""
    call_count = 0

    def create_client(*args, **kwargs):
        """Return different mock based on SSL setting."""
        nonlocal call_count
        call_count += 1
        mock_api = MagicMock()
        mock_api.close = AsyncMock()

        # First call is HTTPS (fails), second call is HTTP (succeeds)
        if call_count == 1:
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidSSLError("SSL certificate verify failed")
            )
        else:
            mock_api.test_connection = AsyncMock(return_value=True)
            mock_api.get_version = AsyncMock(
                return_value={"unraid": "7.2.0", "api": "4.29.2"}
            )
            mock_api.get_server_info = AsyncMock(return_value=create_mock_server_info())
        return mock_api

    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient",
        side_effect=create_client,
    ):
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


async def test_user_flow_unsupported_version_aborts(hass: HomeAssistant) -> None:
    """Test old Unraid version aborts the flow."""
    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_api = MagicMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_version = AsyncMock(
            return_value={"unraid": "6.9.0", "api": "4.10.0"}
        )
        mock_api.close = AsyncMock()
        mock_client.return_value = mock_api

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


async def test_user_flow_cannot_get_version_aborts(hass: HomeAssistant) -> None:
    """Test inability to get version aborts the flow."""
    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_api = MagicMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_version = AsyncMock(side_effect=RuntimeError("API error"))
        mock_api.close = AsyncMock()
        mock_client.return_value = mock_api

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


async def test_user_flow_no_server_uuid_aborts(hass: HomeAssistant) -> None:
    """Test missing server UUID aborts the flow."""
    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_api = MagicMock()
        mock_api.test_connection = AsyncMock(return_value=True)
        mock_api.get_version = AsyncMock(
            return_value={"unraid": "7.2.0", "api": "4.29.2"}
        )
        mock_api.get_server_info = AsyncMock(
            return_value=create_mock_server_info(uuid=None, hostname="tower")
        )
        mock_api.close = AsyncMock()
        mock_client.return_value = mock_api

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
) -> None:
    """Test duplicate server UUID is rejected."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.unraid.config_flow.UnraidClient"
    ) as mock_client:
        mock_client.return_value = create_mock_unraid_client(
            create_mock_server_info(uuid="test-uuid-1234")
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
