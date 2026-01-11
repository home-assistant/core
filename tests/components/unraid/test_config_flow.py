"""Config flow tests for the Unraid integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from unraid_api.exceptions import UnraidAuthenticationError, UnraidConnectionError

from homeassistant import config_entries
from homeassistant.components.unraid.config_flow import (
    CONF_HTTPS_PORT,
    CannotConnectError,
)
from homeassistant.components.unraid.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import _create_mock_server_info


@pytest.fixture
def mock_setup_entry():
    """Mock setup_entry to avoid actual HA component setup."""
    with patch("homeassistant.components.unraid.async_setup_entry", return_value=True):
        yield


def _mock_api_client(
    uuid: str = "test-server-uuid",
    hostname: str = "tower",
    unraid_version: str = "7.2.0",
    api_version: str = "4.29.2",
) -> AsyncMock:
    """Create a mock API client with standard responses."""
    mock_api = AsyncMock()
    mock_api.test_connection = AsyncMock(return_value=True)
    mock_api.get_version = AsyncMock(
        return_value={"unraid": unraid_version, "api": api_version}
    )
    mock_api.get_server_info = AsyncMock(
        return_value=_create_mock_server_info(
            uuid=uuid,
            hostname=hostname,
            unraid_version=unraid_version,
            api_version=api_version,
        )
    )
    mock_api.close = AsyncMock()
    return mock_api


class TestConfigFlow:
    """Test Unraid config flow."""

    async def test_user_step_form_display(self, hass: HomeAssistant) -> None:
        """Test user step shows form with required fields."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "host" in result["data_schema"].schema
        assert "api_key" in result["data_schema"].schema

    async def test_successful_connection(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test successful server connection creates config entry."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "valid-api-key",
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["title"] == "tower"
            assert result["data"]["host"] == "unraid.local"
            assert result["data"]["api_key"] == "valid-api-key"

    async def test_invalid_credentials_error(self, hass: HomeAssistant) -> None:
        """Test invalid API key shows authentication error."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidAuthenticationError("Invalid API key")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "invalid-key",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"][CONF_API_KEY] == "invalid_auth"

    async def test_unreachable_server_error(self, hass: HomeAssistant) -> None:
        """Test unreachable server shows connection error."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidConnectionError("Connection refused")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.invalid",
                    "api_key": "valid-key",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"][CONF_HOST] == "cannot_connect"
            assert result["errors"][CONF_HTTPS_PORT] == "check_port"

    async def test_unsupported_version_error(self, hass: HomeAssistant) -> None:
        """Test old Unraid version shows version error."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(return_value=True)
            mock_api.get_version = AsyncMock(
                return_value={"unraid": "6.9.0", "api": "4.10.0"}
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "valid-key",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "unsupported_version"

    async def test_duplicate_config_entry(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test duplicate server UUID is rejected."""
        # First entry
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client(uuid="same-server-uuid")

            result1 = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "key1",
                },
            )

            assert result1["type"] == FlowResultType.CREATE_ENTRY

        # Second entry with same UUID (different host but same server)
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client(uuid="same-server-uuid")

            result2 = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "192.168.1.100",
                    "api_key": "key2",
                },
            )

            assert result2["type"] == FlowResultType.ABORT
            assert result2["reason"] == "already_configured"

    async def test_user_step_unknown_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test unexpected error during user step gets wrapped as cannot_connect."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(side_effect=RuntimeError("Unexpected"))
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-api-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "cannot_connect"

    async def test_http_error_403_shows_invalid_auth(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test HTTP 403 error is handled as invalid auth."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidAuthenticationError(
                    "Invalid API key or insufficient permissions"
                )
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "bad-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_API_KEY] == "invalid_auth"

    async def test_connection_error_shows_cannot_connect(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test connection error is handled as cannot connect."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidConnectionError("Connection refused")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "cannot_connect"

    async def test_ssl_error_retries_with_verify_disabled(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test SSL errors trigger retry with verify_ssl=False (self-signed certs)."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        call_count = 0

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:

            def create_client(**kwargs: object) -> AsyncMock:
                nonlocal call_count
                call_count += 1
                mock_api = AsyncMock()
                mock_api.close = AsyncMock()

                if kwargs.get("verify_ssl", True) is True:
                    mock_api.test_connection = AsyncMock(
                        side_effect=CannotConnectError("SSL certificate verify failed")
                    )
                else:
                    mock_api.test_connection = AsyncMock(return_value=True)
                    mock_api.get_version = AsyncMock(
                        return_value={"unraid": "7.2.0", "api": "4.29.2"}
                    )
                    mock_api.get_server_info = AsyncMock(
                        return_value=_create_mock_server_info(
                            uuid="test-uuid",
                            hostname="tower",
                        )
                    )

                return mock_api

            MockAPIClient.side_effect = create_client

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-key"},
            )

        assert call_count == 2
        assert result2["type"] == FlowResultType.CREATE_ENTRY

    async def test_ssl_error_shows_cannot_connect_with_hint(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test SSL errors are handled with helpful message."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=Exception("SSL certificate verify failed")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "cannot_connect"

    async def test_authentication_error_shows_invalid_auth(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test UnraidAuthenticationError is detected as auth error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidAuthenticationError("Request unauthorized")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "bad-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_API_KEY] == "invalid_auth"

    async def test_server_error_shows_cannot_connect(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test server error shows cannot connect."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=UnraidConnectionError("HTTP 500: Internal Server Error")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "cannot_connect"

    async def test_user_step_form_includes_port_field(
        self, hass: HomeAssistant
    ) -> None:
        """Test user step shows form with HTTP and HTTPS port fields."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"
        assert "http_port" in result["data_schema"].schema
        assert "https_port" in result["data_schema"].schema

    async def test_successful_connection_with_custom_port(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test successful connection with custom ports creates config entry."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "http_port": 8080,
                    "https_port": 8443,
                    "api_key": "valid-api-key",
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY
            assert result["data"]["host"] == "unraid.local"
            assert result["data"]["http_port"] == 8080
            assert result["data"]["https_port"] == 8443
            assert result["data"]["api_key"] == "valid-api-key"

            MockAPIClient.assert_called_with(
                host="unraid.local",
                api_key="valid-api-key",
                http_port=8080,
                https_port=8443,
                verify_ssl=True,
            )

    async def test_connection_uses_default_port_when_not_specified(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test that default ports 80/443 are used when not specified."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "valid-api-key",
                },
            )

            assert result["type"] == FlowResultType.CREATE_ENTRY

            MockAPIClient.assert_called_with(
                host="unraid.local",
                api_key="valid-api-key",
                http_port=80,
                https_port=443,
                verify_ssl=True,
            )

    async def test_missing_server_uuid_shows_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test connection fails with error when server UUID is not available."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(return_value=True)
            mock_api.get_version = AsyncMock(
                return_value={"unraid": "7.2.0", "api": "4.29.2"}
            )
            mock_api.get_server_info = AsyncMock(
                return_value=_create_mock_server_info(
                    uuid=None,
                    hostname="tower",
                )
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result = await hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": config_entries.SOURCE_USER},
                data={
                    "host": "unraid.local",
                    "api_key": "valid-api-key",
                },
            )

            assert result["type"] == FlowResultType.FORM
            assert result["errors"]["base"] == "no_server_uuid"
