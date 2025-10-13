"""Config flow tests for the Actron Air Integration."""

import asyncio
from unittest.mock import AsyncMock

from actron_neo_api import ActronNeoAuthError

from homeassistant import config_entries
from homeassistant.components.actron_air.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_oauth2_success(
    hass: HomeAssistant, mock_actron_api: AsyncMock
) -> None:
    """Test successful OAuth2 device code flow."""
    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should start with a progress step
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"
    assert result["progress_action"] == "wait_for_authorization"
    assert result["description_placeholders"] is not None
    assert "user_code" in result["description_placeholders"]
    assert result["description_placeholders"]["user_code"] == "ABC123"

    # Wait for the progress to complete
    await hass.async_block_till_done()

    # Continue the flow after progress is done - this should complete the entire flow
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry on successful token exchange
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_API_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == "test_user_id"


async def test_user_flow_oauth2_pending(hass: HomeAssistant, mock_actron_api) -> None:
    """Test OAuth2 flow when authorization is still pending."""

    # Make poll_for_token hang indefinitely to simulate pending state
    async def hang_forever(device_code):
        await asyncio.Event().wait()  # This will never complete

    mock_actron_api.poll_for_token = hang_forever

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should start with a progress step since the task will never complete
    assert result["type"] == FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"
    assert result["progress_action"] == "wait_for_authorization"
    assert result["description_placeholders"] is not None
    assert "user_code" in result["description_placeholders"]
    assert result["description_placeholders"]["user_code"] == "ABC123"

    # The background task should be running but not completed
    # In a real scenario, the user would wait for authorization on their device


async def test_user_flow_oauth2_error(hass: HomeAssistant, mock_actron_api) -> None:
    """Test OAuth2 flow with authentication error during device code request."""
    # Override the default mock to raise an error
    mock_actron_api.request_device_code = AsyncMock(
        side_effect=ActronNeoAuthError("OAuth2 error")
    )

    # Start the flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should abort with oauth2_error
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "oauth2_error"


async def test_user_flow_token_polling_error(
    hass: HomeAssistant, mock_actron_api
) -> None:
    """Test OAuth2 flow with error during token polling."""
    # Override the default mock to raise an error during token polling
    mock_actron_api.poll_for_token = AsyncMock(
        side_effect=ActronNeoAuthError("Token polling error")
    )

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Since the error occurs immediately, the task completes and we get progress_done
    assert result["type"] is FlowResultType.SHOW_PROGRESS_DONE
    assert result["step_id"] == "connection_error"

    # Continue to the connection_error step
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show the connection error form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "connection_error"

    # Now fix the mock to allow successful token polling for recovery
    async def successful_poll_for_token(device_code):
        await asyncio.sleep(0.1)  # Small delay to allow progress state
        return {
            "access_token": "test_access_token",
            "refresh_token": "test_refresh_token",
        }

    mock_actron_api.poll_for_token = successful_poll_for_token

    # User clicks retry button - this should restart the flow and succeed
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    # Should start progress again
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"
    assert result["progress_action"] == "wait_for_authorization"

    # Wait for the progress to complete
    await hass.async_block_till_done()

    # Continue the flow after progress is done - this should complete successfully
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should create entry on successful recovery
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_API_TOKEN: "test_refresh_token",
    }
    assert result["result"].unique_id == "test_user_id"


async def test_user_flow_duplicate_account(
    hass: HomeAssistant, mock_actron_api: AsyncMock
) -> None:
    """Test duplicate account handling - should abort when same account is already configured."""
    # Create an existing config entry for the same user account
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        title="test@example.com",
        data={CONF_API_TOKEN: "existing_refresh_token"},
        unique_id="test_user_id",
    )
    existing_entry.add_to_hass(hass)

    # Start the config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Should start with a progress step
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "user"
    assert result["progress_action"] == "wait_for_authorization"
    assert result["description_placeholders"] is not None
    assert "user_code" in result["description_placeholders"]
    assert result["description_placeholders"]["user_code"] == "ABC123"

    # Wait for the progress to complete
    await hass.async_block_till_done()

    # Continue the flow after progress is done
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort because the account is already configured
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
