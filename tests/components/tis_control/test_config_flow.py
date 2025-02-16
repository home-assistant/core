"""Tests for the TIS Control config flow."""

from unittest.mock import patch

import pytest

# from homeassistant import config_entries
from homeassistant.components.tis_control.config_flow import TISConfigFlow

# from homeassistant.components.tis_control.const import DOMAIN
from homeassistant.const import CONF_PORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def mock_config_flow():
    """Return a mock config flow."""
    return TISConfigFlow()


async def test_show_setup_form(hass: HomeAssistant, mock_config_flow) -> None:
    """Test that the setup form is served."""
    result = await mock_config_flow.async_step_user(user_input=None)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_PORT in result["data_schema"].schema


async def test_invalid_port(hass: HomeAssistant, mock_config_flow) -> None:
    """Test handling of invalid port."""
    with patch.object(mock_config_flow, "validate_port", return_value=False):
        result = await mock_config_flow.async_step_user(user_input={CONF_PORT: 99999})

        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_port"}


async def test_valid_port(hass: HomeAssistant, mock_config_flow) -> None:
    """Test handling of valid port."""
    with patch.object(mock_config_flow, "validate_port", return_value=True):
        result = await mock_config_flow.async_step_user(user_input={CONF_PORT: 1234})

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "TIS Control Bridge"
        assert result["data"] == {CONF_PORT: 1234}


async def test_validate_port() -> None:
    """Test the validate_port method."""
    config_flow = TISConfigFlow()

    assert await config_flow.validate_port(1234) is True
    assert await config_flow.validate_port(0) is False
    assert await config_flow.validate_port(65536) is False
    assert await config_flow.validate_port("invalid") is False
