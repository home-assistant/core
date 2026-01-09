"""Config flow tests for the Unraid integration."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
from aiohttp import ClientConnectorError
import pytest

from homeassistant import config_entries
from homeassistant.components.unraid.config_flow import (
    CONF_HTTP_PORT,
    CONF_HTTPS_PORT,
    CannotConnectError,
)
from homeassistant.components.unraid.const import (
    CONF_STORAGE_INTERVAL,
    CONF_SYSTEM_INTERVAL,
    CONF_UPS_CAPACITY_VA,
    CONF_UPS_NOMINAL_POWER,
    DEFAULT_STORAGE_POLL_INTERVAL,
    DEFAULT_SYSTEM_POLL_INTERVAL,
    DEFAULT_UPS_CAPACITY_VA,
    DEFAULT_UPS_NOMINAL_POWER,
    DOMAIN,
)
from homeassistant.components.unraid.models import UPSDevice
from homeassistant.config_entries import UnknownEntry
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


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
    mock_api.query = AsyncMock(
        return_value={
            "info": {
                "system": {"uuid": uuid},
                "os": {"hostname": hostname},
            }
        }
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
            assert result["title"] == "tower"  # Uses server hostname now
            assert result["data"]["host"] == "unraid.local"
            assert result["data"]["api_key"] == "valid-api-key"

    async def test_invalid_credentials_error(self, hass: HomeAssistant) -> None:
        """Test invalid API key shows authentication error."""
        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=Exception("401: Unauthorized")
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
            # Use ClientError which is simpler to mock
            mock_api.test_connection = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
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
                    "host": "192.168.1.100",  # Different host
                    "api_key": "key2",
                },
            )

            assert result2["type"] == FlowResultType.ABORT
            assert result2["reason"] == "already_configured"

    async def test_hostname_validation(self, hass: HomeAssistant) -> None:
        """Test hostname/IP validation - empty hostname rejected."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "host": "",
                "api_key": "valid-key",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert "host" in result["errors"]

    async def test_api_key_validation(self, hass: HomeAssistant) -> None:
        """Test API key validation - empty key rejected."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                "host": "unraid.local",
                "api_key": "",
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert "api_key" in result["errors"]

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

        # RuntimeError gets wrapped as CannotConnectError by _handle_generic_error
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "cannot_connect"

    async def test_hostname_max_length_validation(self, hass: HomeAssistant) -> None:
        """Test hostname exceeding max length shows error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        # Create hostname that exceeds MAX_HOSTNAME_LEN (254)
        long_hostname = "a" * 255

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: long_hostname, CONF_API_KEY: "valid-api-key"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "invalid_hostname"

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
                side_effect=aiohttp.ClientResponseError(
                    request_info=None, history=(), status=403, message="Forbidden"
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

    async def test_client_connector_error_shows_cannot_connect(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test ClientConnectorError is handled as cannot connect."""

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            conn_key = MagicMock()
            mock_api.test_connection = AsyncMock(
                side_effect=ClientConnectorError(
                    conn_key, OSError("Connection refused")
                )
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

        # Track the number of UnraidClient instantiations and their verify_ssl values
        call_count = 0

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:

            def create_client(**kwargs: object) -> AsyncMock:
                nonlocal call_count
                call_count += 1
                mock_api = AsyncMock()
                mock_api.close = AsyncMock()

                # First call (verify_ssl=True) fails with SSL error
                if kwargs.get("verify_ssl", True) is True:
                    mock_api.test_connection = AsyncMock(
                        side_effect=CannotConnectError("SSL certificate verify failed")
                    )
                else:
                    # Second call (verify_ssl=False) succeeds
                    mock_api.test_connection = AsyncMock(return_value=True)
                    mock_api.get_version = AsyncMock(
                        return_value={"unraid": "7.2.0", "api": "4.29.2"}
                    )
                    mock_api.query = AsyncMock(
                        return_value={
                            "info": {
                                "system": {"uuid": "test-uuid"},
                                "os": {"hostname": "tower"},
                            }
                        }
                    )

                return mock_api

            MockAPIClient.side_effect = create_client

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "valid-key"},
            )

        # Should have been called twice (first with verify_ssl=True, then False)
        assert call_count == 2
        # Should succeed after retry
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

    async def test_unauthorized_in_error_message_shows_invalid_auth(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test 'unauthorized' in error message is detected as auth error."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=Exception("Request unauthorized")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "unraid.local", CONF_API_KEY: "bad-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_API_KEY] == "invalid_auth"

    async def test_http_500_error_shows_cannot_connect(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test HTTP 500 error shows cannot connect."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=aiohttp.ClientResponseError(
                    request_info=None,
                    history=(),
                    status=500,
                    message="Internal Server Error",
                )
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

            # Verify API client was called with the custom ports
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

            # Verify API client was called with default ports 80/443
            MockAPIClient.assert_called_with(
                host="unraid.local",
                api_key="valid-api-key",
                http_port=80,
                https_port=443,
                verify_ssl=True,
            )


class TestReauthFlow:
    """Test Unraid reauth flow."""

    async def test_reauth_flow_shows_form(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth flow shows form for new API key."""
        # Create initial config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data={CONF_HOST: "unraid.local"},
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

    async def test_reauth_flow_success(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test successful reauth updates the config entry."""
        # Create initial config entry
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data={CONF_HOST: "unraid.local"},
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_API_KEY: "new-api-key"},
            )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"
        assert entry.data[CONF_API_KEY] == "new-api-key"

    async def test_reauth_flow_invalid_key(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth with invalid API key shows error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data={CONF_HOST: "unraid.local"},
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=Exception("401: Unauthorized")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_API_KEY: "invalid-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_auth"

    async def test_reauth_flow_missing_entry(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth flow raises UnknownEntry when entry doesn't exist."""

        # When reauth is initiated with a nonexistent entry_id, Home Assistant
        # raises UnknownEntry during form display (when accessing _get_reauth_entry())
        with pytest.raises(UnknownEntry):
            await hass.config_entries.flow.async_init(
                DOMAIN,
                context={
                    "source": config_entries.SOURCE_REAUTH,
                    "entry_id": "nonexistent-entry-id",
                },
                data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            )

    async def test_reauth_flow_cannot_connect_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth flow shows connection error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_API_KEY: "new-api-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"

    async def test_reauth_flow_unsupported_version_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth flow shows unsupported version error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock()
            mock_api.get_version = AsyncMock(
                return_value={"api": "0.0.1", "unraid": "6.0.0"}  # Old version
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_API_KEY: "new-api-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "unsupported_version"

    async def test_reauth_flow_unknown_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reauth flow wraps unexpected exceptions as cannot_connect."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_REAUTH,
                "entry_id": entry.entry_id,
            },
            data=entry.data,
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
                {CONF_API_KEY: "new-api-key"},
            )

        # RuntimeError gets wrapped as CannotConnectError by _handle_generic_error
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"


class TestOptionsFlow:
    """Test Unraid options flow."""

    async def test_options_flow_shows_form_without_ups(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test options flow shows form without UPS options when no UPS detected."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "key"},
            options={
                CONF_SYSTEM_INTERVAL: 60,
                CONF_STORAGE_INTERVAL: 600,
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        # No runtime_data means no UPS detected
        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        # UPS options should not be in schema when no UPS detected
        schema_keys = list(result["data_schema"].schema.keys())
        schema_key_names = [str(k) for k in schema_keys]
        assert CONF_UPS_CAPACITY_VA not in schema_key_names
        assert CONF_UPS_NOMINAL_POWER not in schema_key_names

    async def test_options_flow_shows_ups_options_when_ups_detected(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test options flow shows UPS options when UPS is detected."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "key"},
            options={
                CONF_SYSTEM_INTERVAL: 60,
                CONF_STORAGE_INTERVAL: 600,
                CONF_UPS_CAPACITY_VA: 1000,
                CONF_UPS_NOMINAL_POWER: 800,
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        # Mock runtime_data with UPS device
        @dataclass
        class MockSystemData:
            ups_devices: list

        @dataclass
        class MockRuntimeData:
            system_coordinator: MagicMock

        mock_coordinator = MagicMock()
        mock_coordinator.data = MockSystemData(
            ups_devices=[UPSDevice(id="ups:1", name="APC")]
        )
        entry.runtime_data = MockRuntimeData(system_coordinator=mock_coordinator)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "init"
        # UPS options should be in schema when UPS detected
        schema_keys = list(result["data_schema"].schema.keys())
        schema_key_names = [str(k) for k in schema_keys]
        assert CONF_UPS_CAPACITY_VA in schema_key_names
        assert CONF_UPS_NOMINAL_POWER in schema_key_names

    async def test_options_flow_saves_values_without_ups(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test options flow saves values when no UPS is present."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "key"},
            options={
                CONF_SYSTEM_INTERVAL: DEFAULT_SYSTEM_POLL_INTERVAL,
                CONF_STORAGE_INTERVAL: DEFAULT_STORAGE_POLL_INTERVAL,
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SYSTEM_INTERVAL: 45,
                CONF_STORAGE_INTERVAL: 120,
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_SYSTEM_INTERVAL] == 45
        assert entry.options[CONF_STORAGE_INTERVAL] == 120

    async def test_options_flow_saves_values_with_ups(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test options flow saves UPS values when UPS is present."""

        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "key"},
            options={
                CONF_SYSTEM_INTERVAL: DEFAULT_SYSTEM_POLL_INTERVAL,
                CONF_STORAGE_INTERVAL: DEFAULT_STORAGE_POLL_INTERVAL,
                CONF_UPS_CAPACITY_VA: DEFAULT_UPS_CAPACITY_VA,
                CONF_UPS_NOMINAL_POWER: DEFAULT_UPS_NOMINAL_POWER,
            },
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        # Mock runtime_data with UPS device
        @dataclass
        class MockSystemData:
            ups_devices: list

        @dataclass
        class MockRuntimeData:
            system_coordinator: MagicMock

        mock_coordinator = MagicMock()
        mock_coordinator.data = MockSystemData(
            ups_devices=[UPSDevice(id="ups:1", name="APC")]
        )
        entry.runtime_data = MockRuntimeData(system_coordinator=mock_coordinator)

        result = await hass.config_entries.options.async_init(entry.entry_id)

        result2 = await hass.config_entries.options.async_configure(
            result["flow_id"],
            {
                CONF_SYSTEM_INTERVAL: 45,
                CONF_STORAGE_INTERVAL: 120,
                CONF_UPS_CAPACITY_VA: 1500,
                CONF_UPS_NOMINAL_POWER: 1200,
            },
        )

        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_SYSTEM_INTERVAL] == 45
        assert entry.options[CONF_STORAGE_INTERVAL] == 120
        assert entry.options[CONF_UPS_CAPACITY_VA] == 1500
        assert entry.options[CONF_UPS_NOMINAL_POWER] == 1200


class TestReconfigureFlow:
    """Test Unraid reconfigure flow."""

    async def test_reconfigure_flow_shows_form(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow shows form with current values."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

    async def test_reconfigure_flow_success(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test successful reconfigure updates the config entry."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "192.168.1.100", CONF_API_KEY: "new-key"},
            )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"
        assert entry.data[CONF_HOST] == "192.168.1.100"
        assert entry.data[CONF_API_KEY] == "new-key"

    async def test_reconfigure_flow_connection_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure with connection error shows error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=aiohttp.ClientError("Connection refused")
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "192.168.1.100", CONF_API_KEY: "new-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"

    async def test_reconfigure_flow_missing_entry(self, hass: HomeAssistant) -> None:
        """Test reconfigure flow aborts when entry is missing."""
        # Start reconfigure with invalid entry_id
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": "nonexistent-entry",
            },
        )

        # Should abort immediately
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "reconfigure_failed"

    async def test_reconfigure_flow_validation_errors(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow shows validation errors."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        # Submit with empty host
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_HOST: "", CONF_API_KEY: "new-key"},
        )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"][CONF_HOST] == "required"

    async def test_reconfigure_flow_invalid_auth_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow shows invalid auth error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock(
                side_effect=aiohttp.ClientResponseError(
                    request_info=None, history=(), status=401, message="Unauthorized"
                )
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "192.168.1.100", CONF_API_KEY: "bad-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "invalid_auth"

    async def test_reconfigure_flow_unsupported_version_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow shows unsupported version error."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            mock_api = AsyncMock()
            mock_api.test_connection = AsyncMock()
            mock_api.get_version = AsyncMock(
                return_value={"api": "0.0.1", "unraid": "6.0.0"}
            )
            mock_api.close = AsyncMock()
            MockAPIClient.return_value = mock_api

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {CONF_HOST: "192.168.1.100", CONF_API_KEY: "new-key"},
            )

        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "unsupported_version"

    async def test_reconfigure_flow_unknown_error(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow wraps unexpected exceptions as cannot_connect."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={CONF_HOST: "unraid.local", CONF_API_KEY: "old-key"},
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
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
                {CONF_HOST: "192.168.1.100", CONF_API_KEY: "new-key"},
            )

        # RuntimeError gets wrapped as CannotConnectError by _handle_generic_error
        assert result2["type"] == FlowResultType.FORM
        assert result2["errors"]["base"] == "cannot_connect"

    async def test_reconfigure_flow_shows_port_field(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow shows form with HTTP and HTTPS port fields."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "unraid.local",
                CONF_HTTP_PORT: 8080,
                CONF_HTTPS_PORT: 8443,
                CONF_API_KEY: "old-key",
            },
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "reconfigure"
        assert "http_port" in result["data_schema"].schema
        assert "https_port" in result["data_schema"].schema

    async def test_reconfigure_flow_updates_port(
        self, hass: HomeAssistant, mock_setup_entry: None
    ) -> None:
        """Test reconfigure flow can update the ports."""
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="tower",
            data={
                CONF_HOST: "unraid.local",
                CONF_HTTP_PORT: 80,
                CONF_HTTPS_PORT: 443,
                CONF_API_KEY: "old-key",
            },
            options={},
            unique_id="test-uuid",
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_RECONFIGURE,
                "entry_id": entry.entry_id,
            },
        )

        with patch(
            "homeassistant.components.unraid.config_flow.UnraidClient"
        ) as MockAPIClient:
            MockAPIClient.return_value = _mock_api_client()

            result2 = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                {
                    CONF_HOST: "unraid.local",
                    CONF_HTTP_PORT: 8080,
                    CONF_HTTPS_PORT: 8443,
                    CONF_API_KEY: "new-key",
                },
            )

        assert result2["type"] == FlowResultType.ABORT
        assert result2["reason"] == "reconfigure_successful"
        assert entry.data[CONF_HTTP_PORT] == 8080
        assert entry.data[CONF_HTTPS_PORT] == 8443
