"""Test config flow for Hisense AC Plugin."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hisense_connectlife.config_flow import OAuth2FlowHandler
from custom_components.hisense_connectlife.const import DOMAIN


@pytest.mark.asyncio
async def test_user_step_initial_form(mock_hass):
    """Test initial user step shows form."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert "confirm_auth" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_user_step_with_input(mock_hass, mock_oauth2_implementation):
    """Test user step with user input."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass

    with patch("custom_components.hisense_connectlife.config_flow.HisenseOAuth2Implementation") as mock_impl:
        mock_impl.return_value = mock_oauth2_implementation
        
        result = await flow.async_step_user({"confirm_auth": True})

        assert result["type"] == FlowResultType.EXTERNAL_STEP
        assert result["step_id"] == "auth"
        assert "url" in result


@pytest.mark.asyncio
async def test_oauth_create_entry(mock_hass, mock_oauth2_implementation):
    """Test OAuth create entry step."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
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
async def test_single_instance_allowed(mock_hass):
    """Test that only one instance is allowed."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass

    # Mock existing entries
    mock_hass.config_entries.async_entries.return_value = [MagicMock()]

    result = await flow.async_step_user()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.asyncio
async def test_authorize_url_fail(mock_hass, mock_oauth2_implementation):
    """Test authorize URL generation failure."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass

    # Mock implementation that raises exception
    mock_oauth2_implementation.async_generate_authorize_url.side_effect = Exception("Test error")

    with patch("custom_components.hisense_connectlife.config_flow.HisenseOAuth2Implementation") as mock_impl:
        mock_impl.return_value = mock_oauth2_implementation
        
        result = await flow.async_step_user({"confirm_auth": True})

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "authorize_url_fail"


@pytest.mark.asyncio
async def test_options_flow(mock_config_entry, mock_hass):
    """Test options flow."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass

    # Test initial form
    result = await flow.async_step_init()

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"
    assert "refresh_devices" in result["data_schema"].schema
    assert "refresh_token" in result["data_schema"].schema


@pytest.mark.asyncio
async def test_options_flow_refresh_devices(mock_config_entry, mock_hass, mock_coordinator):
    """Test options flow refresh devices."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass
    flow.hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    result = await flow.async_step_init({"refresh_devices": True})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is True


@pytest.mark.asyncio
async def test_options_flow_refresh_token(mock_config_entry, mock_hass, mock_coordinator):
    """Test options flow refresh token."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass
    flow.hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    result = await flow.async_step_init({"refresh_token": True})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_token"] is True


@pytest.mark.asyncio
async def test_oauth_create_entry_with_error(mock_hass, mock_oauth2_implementation):
    """Test OAuth create entry step with error."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.flow_impl = mock_oauth2_implementation

    # Mock implementation that raises exception
    mock_oauth2_implementation.async_resolve_external_data.side_effect = Exception("Test error")

    data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.asyncio
async def test_oauth_create_entry_missing_token(mock_hass, mock_oauth2_implementation):
    """Test OAuth create entry step with missing token."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.flow_impl = mock_oauth2_implementation

    data = {
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.asyncio
async def test_oauth_create_entry_invalid_data(mock_hass, mock_oauth2_implementation):
    """Test OAuth create entry step with invalid data."""
    flow = OAuth2FlowHandler()
    flow.hass = mock_hass
    flow.flow_impl = mock_oauth2_implementation

    # Mock implementation that returns None
    mock_oauth2_implementation.async_resolve_external_data.return_value = None

    data = {
        "access_token": "test_token",
        "refresh_token": "test_refresh",
        "expires_in": 3600,
    }

    result = await flow.async_oauth_create_entry(data)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "oauth_error"


@pytest.mark.asyncio
async def test_options_flow_no_coordinator(mock_config_entry, mock_hass):
    """Test options flow when coordinator is not available."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass
    flow.hass.data[DOMAIN] = {}

    result = await flow.async_step_init({"refresh_devices": True})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is True


@pytest.mark.asyncio
async def test_options_flow_both_actions(mock_config_entry, mock_hass, mock_coordinator):
    """Test options flow with both actions selected."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass
    flow.hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    result = await flow.async_step_init({
        "refresh_devices": True,
        "refresh_token": True
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is True
    assert result["data"]["refresh_token"] is True


@pytest.mark.asyncio
async def test_options_flow_no_actions(mock_config_entry, mock_hass, mock_coordinator):
    """Test options flow with no actions selected."""
    from custom_components.hisense_connectlife.config_flow import HisenseOptionsFlowHandler

    flow = HisenseOptionsFlowHandler(mock_config_entry)
    flow.hass = mock_hass
    flow.hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_coordinator}

    result = await flow.async_step_init({
        "refresh_devices": False,
        "refresh_token": False
    })

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"]["refresh_devices"] is False
    assert result["data"]["refresh_token"] is False
