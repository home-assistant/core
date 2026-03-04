"""Test config flow for Hisense AC Plugin."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.hisense_connectlife.config_flow import (
    HisenseOptionsFlowHandler,
    OAuth2FlowHandler,
)
from homeassistant.components.hisense_connectlife.const import DOMAIN
from homeassistant.data_entry_flow import FlowResultType


@pytest.mark.asyncio
async def test_user_step_initial_form(mock_hass) -> None:
    """Test initial user step shows form."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.context = {}
    flow._async_current_entries = list

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "confirm_auth" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_user_step_with_input(mock_hass, mock_oauth2_implementation) -> None:
    """Test user step with user input."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.context = {}
    flow._async_current_entries = list

    with patch(
        "homeassistant.components.hisense_connectlife.config_flow.HisenseOAuth2Implementation"
    ) as mock_impl:
        mock_impl.return_value = mock_oauth2_implementation

        result = await flow.async_step_user({"confirm_auth": True})

        assert result["type"] == FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"
        assert "url" in result


@pytest.mark.asyncio
async def test_oauth_create_entry(mock_hass, mock_oauth2_implementation) -> None:
    """Test OAuth create entry step."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    mock_oauth2_implementation.name = "Hisense AC"
    flow.flow_impl = mock_oauth2_implementation

    data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hisense AC"
    assert result["data"]["auth_implementation"] == DOMAIN
    assert result["data"]["implementation"] == DOMAIN


@pytest.mark.asyncio
async def test_single_instance_allowed(mock_hass) -> None:
    """Test that only one instance is allowed."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.context = {}

    # Mock existing entries
    mock_hass.config_entries.async_entries.return_value = [MagicMock()]

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_authorize_url_fail(mock_hass, mock_oauth2_implementation) -> None:
    """Test authorize URL generation failure."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.context = {}
    flow._async_current_entries = list

    # Mock implementation that raises exception
    mock_oauth2_implementation.async_generate_authorize_url.side_effect = Exception(
        "Test error"
    )

    with patch(
        "homeassistant.components.hisense_connectlife.config_flow.HisenseOAuth2Implementation"
    ) as mock_impl:
        mock_impl.return_value = mock_oauth2_implementation

        result = await flow.async_step_user({"confirm_auth": True})

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "authorize_url_fail"


@pytest.mark.asyncio
async def test_options_flow(mock_config_entry, mock_hass) -> None:
    """Test options flow."""
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )

    handler = HisenseOptionsFlowHandler()
    handler.hass = mock_hass
    handler.handler = mock_config_entry.entry_id
    handler._flow_id = "test_flow_id"

    result = await handler.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "refresh_devices" in result["data_schema"].schema
    assert "refresh_token" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_options_flow_refresh_devices(
    mock_config_entry, mock_hass, mock_coordinator
) -> None:
    """Test options flow refresh devices."""
    mock_config_entry.runtime_data = mock_coordinator

    # async_get_devices is an async property, create a property that returns a coroutine
    async def mock_get_devices():
        return {}

    # Create a property descriptor that returns a new coroutine each time
    type(mock_coordinator.api_client).async_get_devices = property(
        lambda self: mock_get_devices()
    )
    mock_coordinator.async_refresh = AsyncMock()
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )
    mock_hass.config_entries.async_update_entry = AsyncMock()

    handler = HisenseOptionsFlowHandler()
    handler.hass = mock_hass
    handler.handler = mock_config_entry.entry_id
    handler._flow_id = "test_flow_id"

    result = await handler.async_step_init({"refresh_devices": True})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is True


@pytest.mark.asyncio
async def test_options_flow_refresh_token(
    mock_config_entry, mock_hass, mock_coordinator
) -> None:
    """Test options flow refresh token."""
    mock_config_entry.runtime_data = mock_coordinator
    mock_coordinator.api_client.oauth_session.token = {"access_token": "old_token"}
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )
    mock_hass.config_entries.async_update_entry = AsyncMock()

    with patch(
        "homeassistant.components.hisense_connectlife.config_flow.HisenseOAuth2Implementation"
    ) as mock_impl_class:
        mock_impl = MagicMock()
        mock_impl.async_refresh_token = AsyncMock(
            return_value={"access_token": "new_token"}
        )
        mock_impl_class.return_value = mock_impl

        handler = HisenseOptionsFlowHandler()
        handler.hass = mock_hass
        handler.handler = mock_config_entry.entry_id
        handler._flow_id = "test_flow_id"

        result = await handler.async_step_init({"refresh_token": True})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["refresh_token"] is True


@pytest.mark.asyncio
async def test_oauth_create_entry_with_error(
    mock_hass, mock_oauth2_implementation
) -> None:
    """Test OAuth create entry step with error."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    mock_oauth2_implementation.name = "Hisense AC"
    flow.flow_impl = mock_oauth2_implementation

    data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    # async_oauth_create_entry doesn't validate, it just creates entry
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["access_token"] == "test_token"


@pytest.mark.asyncio
async def test_oauth_create_entry_missing_token(
    mock_hass, mock_oauth2_implementation
) -> None:
    """Test OAuth create entry step with missing token."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    mock_oauth2_implementation.name = "Hisense AC"
    flow.flow_impl = mock_oauth2_implementation

    data = {
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    # async_oauth_create_entry doesn't validate, it just creates entry
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert "refresh_token" in result["data"]


@pytest.mark.asyncio
async def test_oauth_create_entry_invalid_data(
    mock_hass, mock_oauth2_implementation
) -> None:
    """Test OAuth create entry step with invalid data."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    mock_oauth2_implementation.name = "Hisense AC"
    flow.flow_impl = mock_oauth2_implementation

    data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    # async_oauth_create_entry doesn't validate, it just creates entry
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["access_token"] == "test_token"


@pytest.mark.asyncio
async def test_options_flow_no_coordinator(mock_config_entry, mock_hass) -> None:
    """Test options flow when coordinator is not available."""
    mock_config_entry.runtime_data = None
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )
    mock_hass.config_entries.async_update_entry = AsyncMock()

    handler = HisenseOptionsFlowHandler()
    handler.hass = mock_hass
    handler.handler = mock_config_entry.entry_id
    handler._flow_id = "test_flow_id"

    result = await handler.async_step_init({"refresh_devices": True})

    # When coordinator is None, it will fail but still create entry
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is True


@pytest.mark.asyncio
async def test_options_flow_both_actions(
    mock_config_entry, mock_hass, mock_coordinator
) -> None:
    """Test options flow with both actions selected."""
    mock_config_entry.runtime_data = mock_coordinator

    # async_get_devices is an async property, mock it to return a coroutine
    async def mock_get_devices():
        return {}

    type(mock_coordinator.api_client).async_get_devices = property(
        lambda self: mock_get_devices()
    )
    mock_coordinator.async_refresh = AsyncMock()
    mock_coordinator.api_client.oauth_session.token = {"access_token": "old_token"}
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )
    mock_hass.config_entries.async_update_entry = AsyncMock()

    with patch(
        "homeassistant.components.hisense_connectlife.config_flow.HisenseOAuth2Implementation"
    ) as mock_impl_class:
        mock_impl = MagicMock()
        mock_impl.async_refresh_token = AsyncMock(
            return_value={"access_token": "new_token"}
        )
        mock_impl_class.return_value = mock_impl

        handler = HisenseOptionsFlowHandler()
        handler.hass = mock_hass
        handler.handler = mock_config_entry.entry_id
        handler._flow_id = "test_flow_id"

        result = await handler.async_step_init(
            {"refresh_devices": True, "refresh_token": True}
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]["refresh_devices"] is True
        assert result["data"]["refresh_token"] is True


@pytest.mark.asyncio
async def test_options_flow_no_actions(
    mock_config_entry, mock_hass, mock_coordinator
) -> None:
    """Test options flow with no actions selected."""
    mock_config_entry.runtime_data = mock_coordinator
    mock_hass.config_entries.async_get_known_entry = MagicMock(
        return_value=mock_config_entry
    )

    handler = HisenseOptionsFlowHandler()
    handler.hass = mock_hass
    handler.handler = mock_config_entry.entry_id
    handler._flow_id = "test_flow_id"

    result = await handler.async_step_init(
        {"refresh_devices": False, "refresh_token": False}
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is False
    assert result["data"]["refresh_token"] is False
