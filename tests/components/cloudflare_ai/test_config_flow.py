"""Tests for the Cloudflare Workers AI config flow."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.cloudflare_ai.client import (
    CloudflareAIAuthError,
    CloudflareAIConnectionError,
)
from homeassistant.components.cloudflare_ai.const import (
    CONF_ACCOUNT_ID,
    CONF_API_TOKEN,
    CONF_GATEWAY_API_TOKEN,
    CONF_GATEWAY_ID,
    CONF_USE_AI_GATEWAY,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

from .conftest import TEST_ACCOUNT_ID, TEST_API_TOKEN

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def mock_setup_entry(hass: HomeAssistant) -> AsyncGenerator[None]:
    """Prevent full setup during config flow tests."""
    # Set up conversation component (required dependency)
    # by setting up homeassistant and conversation components
    await async_setup_component(hass, "homeassistant", {})
    await async_setup_component(hass, "conversation", {})
    await hass.async_block_till_done()

    with patch(
        "homeassistant.components.cloudflare_ai.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_user_step_success(hass: HomeAssistant) -> None:
    """Test successful user step."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == "Cloudflare Workers AI"
        assert result["data"][CONF_ACCOUNT_ID] == TEST_ACCOUNT_ID
        assert result["data"][CONF_API_TOKEN] == TEST_API_TOKEN
        assert result["data"][CONF_USE_AI_GATEWAY] is False
        # Should create 1 default subentry (conversation)
        assert len(result.get("subentries", [])) == 1


async def test_user_step_with_gateway(hass: HomeAssistant) -> None:
    """Test user step with AI Gateway enabled."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: True,
                CONF_GATEWAY_ID: "my-gateway",
                CONF_GATEWAY_API_TOKEN: "gw-token",
            },
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_USE_AI_GATEWAY] is True
        assert result["data"][CONF_GATEWAY_ID] == "my-gateway"
        assert result["data"][CONF_GATEWAY_API_TOKEN] == "gw-token"


async def test_user_step_invalid_auth(hass: HomeAssistant) -> None:
    """Test user step with invalid credentials."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIAuthError("Invalid token"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: "bad_token",
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


async def test_user_step_cannot_connect(hass: HomeAssistant) -> None:
    """Test user step when API is unreachable."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIConnectionError("Connection failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_user_step_duplicate_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that duplicate accounts are rejected."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "new_token_123"},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert mock_config_entry.data[CONF_API_TOKEN] == "new_token_123"


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the main entry reconfigure flow."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: "new_account_id",
                CONF_API_TOKEN: "new_token",
                CONF_USE_AI_GATEWAY: True,
                CONF_GATEWAY_ID: "my-gw",
                CONF_GATEWAY_API_TOKEN: "gw-token",
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert mock_config_entry.data[CONF_ACCOUNT_ID] == "new_account_id"
        assert mock_config_entry.data[CONF_USE_AI_GATEWAY] is True
        assert mock_config_entry.data[CONF_GATEWAY_ID] == "my-gw"


async def test_user_step_missing_gateway_id(hass: HomeAssistant) -> None:
    """Test user step with gateway enabled but no gateway ID."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: True,
                CONF_GATEWAY_ID: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "missing_gateway_id"


async def test_user_step_unknown_error(hass: HomeAssistant) -> None:
    """Test user step with unexpected error."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: TEST_API_TOKEN,
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with invalid token."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIAuthError("Invalid token"),
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "still_bad"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


async def test_reauth_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with connection error."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIConnectionError("Down"),
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "token"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with unexpected error."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=RuntimeError("oops"),
    ):
        result = await mock_config_entry.start_reauth_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_TOKEN: "token"},
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


async def test_reconfigure_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with invalid auth."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIAuthError("bad"),
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: "wrong",
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "invalid_auth"


async def test_reconfigure_cannot_connect(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with connection error."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=CloudflareAIConnectionError("net"),
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: "tok",
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "cannot_connect"


async def test_reconfigure_unknown_error(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with unexpected error."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        side_effect=RuntimeError("?"),
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: "tok",
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "unknown"


async def test_reconfigure_missing_gateway_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow with gateway enabled but no gateway ID."""
    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: TEST_ACCOUNT_ID,
                CONF_API_TOKEN: "tok",
                CONF_USE_AI_GATEWAY: True,
                CONF_GATEWAY_ID: "",
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"]["base"] == "missing_gateway_id"


async def test_reconfigure_duplicate_account(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure aborts when changing to an existing account ID."""
    # Add a second entry with a different account ID
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Other",
        data={
            CONF_ACCOUNT_ID: "other_account",
            CONF_API_TOKEN: "other_token",
            CONF_USE_AI_GATEWAY: False,
        },
        unique_id="other_account",
    )
    other_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.cloudflare_ai.config_flow.CloudflareAIClient.validate_credentials",
        new_callable=AsyncMock,
        return_value=True,
    ):
        result = await mock_config_entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_ACCOUNT_ID: "other_account",
                CONF_API_TOKEN: "any",
                CONF_USE_AI_GATEWAY: False,
            },
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_conversation_subentry_create(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test creating a new conversation subentry."""
    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, "conversation"),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {
            "name": "My Agent",
            "max_tokens": 1024,
            "temperature": 0.6,
            "enable_thinking": False,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My Agent"


async def test_conversation_subentry_reconfigure(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfiguring an existing conversation subentry."""
    subentry = next(iter(mock_config_entry.subentries.values()))
    subentry_flow = await mock_config_entry.start_subentry_reconfigure_flow(
        hass, subentry.subentry_id
    )
    assert subentry_flow["type"] is FlowResultType.FORM
    assert subentry_flow["step_id"] == "init"

    result = await hass.config_entries.subentries.async_configure(
        subentry_flow["flow_id"],
        {
            "max_tokens": 2048,
            "temperature": 0.8,
            "enable_thinking": False,
        },
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
