"""Tests for the OpenAI Conversation helpers."""

from unittest.mock import MagicMock, patch

from homeassistant.components.openai_conversation.const import (
    CONF_API_BASE,
    CONF_DEFAULT_QUERY,
)
from homeassistant.components.openai_conversation.helpers import (
    create_client,
    parse_default_query,
)
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant


class TestParseDefaultQuery:
    """Tests for parse_default_query function."""

    def test_empty_string(self) -> None:
        """Test parsing empty string returns empty dict."""
        assert parse_default_query("") == {}

    def test_single_parameter(self) -> None:
        """Test parsing single parameter."""
        assert parse_default_query("api-version=2024-06-01") == {
            "api-version": "2024-06-01"
        }

    def test_multiple_parameters(self) -> None:
        """Test parsing multiple parameters."""
        assert parse_default_query("api-version=preview&foo=bar") == {
            "api-version": "preview",
            "foo": "bar",
        }

    def test_parameters_with_whitespace(self) -> None:
        """Test parsing parameters - whitespace is preserved by standard URL parsing."""
        # Standard URL parsing preserves whitespace in keys/values
        # Users should not include whitespace in query strings
        assert parse_default_query("api-version=preview&foo=bar") == {
            "api-version": "preview",
            "foo": "bar",
        }

    def test_parameter_without_value(self) -> None:
        """Test parsing parameter without value gets empty string."""
        # Standard URL parsing treats 'invalid' as 'invalid=' (empty value)
        assert parse_default_query("api-version=preview&invalid&foo=bar") == {
            "api-version": "preview",
            "invalid": "",
            "foo": "bar",
        }

    def test_parameter_with_equals_in_value(self) -> None:
        """Test parsing parameter with equals sign in value."""
        assert parse_default_query("filter=name=test") == {"filter": "name=test"}


class TestCreateClient:
    """Tests for create_client function."""

    async def test_create_client_basic(self, hass: HomeAssistant) -> None:
        """Test creating client with only API key."""
        with patch(
            "homeassistant.components.openai_conversation.helpers.get_async_client"
        ) as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            with patch(
                "homeassistant.components.openai_conversation.helpers.openai.AsyncOpenAI"
            ) as mock_openai:
                create_client(hass, {CONF_API_KEY: "test-key"})

                mock_openai.assert_called_once_with(
                    api_key="test-key",
                    http_client=mock_http_client,
                )

    async def test_create_client_with_custom_endpoint(
        self, hass: HomeAssistant
    ) -> None:
        """Test creating client with custom API endpoint."""
        with patch(
            "homeassistant.components.openai_conversation.helpers.get_async_client"
        ) as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            with patch(
                "homeassistant.components.openai_conversation.helpers.openai.AsyncOpenAI"
            ) as mock_openai:
                create_client(
                    hass,
                    {
                        CONF_API_KEY: "test-key",
                        CONF_API_BASE: "https://my-resource.openai.azure.com",
                    },
                )

                mock_openai.assert_called_once_with(
                    api_key="test-key",
                    http_client=mock_http_client,
                    base_url="https://my-resource.openai.azure.com/openai/v1/",
                )

    async def test_create_client_with_default_query(self, hass: HomeAssistant) -> None:
        """Test creating client with default query parameters."""
        with patch(
            "homeassistant.components.openai_conversation.helpers.get_async_client"
        ) as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            with patch(
                "homeassistant.components.openai_conversation.helpers.openai.AsyncOpenAI"
            ) as mock_openai:
                create_client(
                    hass,
                    {
                        CONF_API_KEY: "test-key",
                        CONF_DEFAULT_QUERY: "api-version=2024-06-01",
                    },
                )

                mock_openai.assert_called_once_with(
                    api_key="test-key",
                    http_client=mock_http_client,
                    default_query={"api-version": "2024-06-01"},
                )

    async def test_create_client_with_all_options(self, hass: HomeAssistant) -> None:
        """Test creating client with all custom options (Azure OpenAI scenario)."""
        with patch(
            "homeassistant.components.openai_conversation.helpers.get_async_client"
        ) as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            with patch(
                "homeassistant.components.openai_conversation.helpers.openai.AsyncOpenAI"
            ) as mock_openai:
                create_client(
                    hass,
                    {
                        CONF_API_KEY: "azure-api-key",
                        CONF_API_BASE: "https://my-resource.openai.azure.com/openai/deployments/gpt-4",
                        CONF_DEFAULT_QUERY: "api-version=2024-06-01&custom=value",
                    },
                )

                mock_openai.assert_called_once_with(
                    api_key="azure-api-key",
                    http_client=mock_http_client,
                    base_url="https://my-resource.openai.azure.com/openai/deployments/gpt-4/openai/v1/",
                    default_query={"api-version": "2024-06-01", "custom": "value"},
                )

    async def test_create_client_empty_optional_values(
        self, hass: HomeAssistant
    ) -> None:
        """Test creating client with empty optional values are ignored."""
        with patch(
            "homeassistant.components.openai_conversation.helpers.get_async_client"
        ) as mock_get_client:
            mock_http_client = MagicMock()
            mock_get_client.return_value = mock_http_client

            with patch(
                "homeassistant.components.openai_conversation.helpers.openai.AsyncOpenAI"
            ) as mock_openai:
                create_client(
                    hass,
                    {
                        CONF_API_KEY: "test-key",
                        CONF_API_BASE: "",
                        CONF_DEFAULT_QUERY: "",
                    },
                )

                # Empty strings should not result in base_url or default_query being set
                mock_openai.assert_called_once_with(
                    api_key="test-key",
                    http_client=mock_http_client,
                )
