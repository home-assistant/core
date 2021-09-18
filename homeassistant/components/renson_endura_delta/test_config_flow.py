"""Tests for config flow."""
from unittest.mock import MagicMock

from homeassistant.components.renson_endura_delta.config_flow import (
    CannotConnect,
    ConfigFlow,
    PlaceholderHub,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult


async def test_config_flow_no_user_input():
    """Test no user input scenario."""
    hub = PlaceholderHub("localhost", HomeAssistant())
    hub.connect = MagicMock(return_value=True)

    result = FlowResult()
    config_flow = ConfigFlow()
    config_flow.async_show_form = MagicMock(return_value=result)
    actual: FlowResult = await config_flow.async_step_user(None)

    assert config_flow.async_show_form.called

    assert result == actual


async def test_config_flow_incorrect_user_input():
    """Test wrong user input scenario."""
    hub = PlaceholderHub("localhost", HomeAssistant())
    hub.connect = MagicMock(return_value=False)

    result = FlowResult()
    config_flow = ConfigFlow()
    config_flow.async_show_form = MagicMock(return_value=result)
    config_flow.validate_input = MagicMock(side_effect=CannotConnect)
    actual: FlowResult = await config_flow.async_step_user({"host": "localhost"})

    assert config_flow.async_show_form.called
    assert result == actual
