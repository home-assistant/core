from homeassistant import config_entries, data_entry_flow
from homeassistant.components.redgtech.config_flow import RedgtechConfigFlow
from homeassistant.components.redgtech.const import DOMAIN
import aiohttp
import asyncio
import pytest
from unittest.mock import patch

@pytest.fixture
def mock_flow():
    """Return a mock config flow."""
    return RedgtechConfigFlow()

async def test_show_form(mock_flow):
    """Test that the form is shown."""
    result = await mock_flow.async_step_user()
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

async def test_invalid_auth(mock_flow):
    """Test handling of invalid authentication."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 401
        result = await mock_flow.async_step_user({"email": "test@test.com", "password": "wrongpassword"})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_auth"}

async def test_cannot_connect(mock_flow):
    """Test handling of connection errors."""
    with patch("aiohttp.ClientSession.post", side_effect=aiohttp.ClientError):
        result = await mock_flow.async_step_user({"email": "test@test.com", "password": "password"})
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

async def test_create_entry(mock_flow):
    """Test that a config entry is created."""
    with patch("aiohttp.ClientSession.post") as mock_post:
        mock_post.return_value.__aenter__.return_value.status = 200
        mock_post.return_value.__aenter__.return_value.json.return_value = {
            "data": {"access_token": "test_token"}
        }
        result = await mock_flow.async_step_user({"email": "test@test.com", "password": "password"})
        assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
        assert result["title"] == "Redgtech"
        assert result["data"] == {"access_token": "test_token"}