"""Test the TISControl config flow."""

from unittest.mock import patch

from homeassistant.components.tis_control.config_flow import TISConfigFlow
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_initial_form_display(hass: HomeAssistant) -> None:
    """Test form display."""
    flow = TISConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(None)
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]


async def test_user_input_valid_port(hass: HomeAssistant) -> None:
    """Test valid input."""
    flow = TISConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user({"port": 1234})
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert isinstance(result["title"], str)
    assert result["data"] == {"port": 1234}
    # make sure no errors
    assert "errors" not in result


async def test_user_input_port_invalid_characters(hass: HomeAssistant) -> None:
    """Test input where port contains invalid characters."""
    flow = TISConfigFlow()
    flow.hass = hass
    with patch(
        "homeassistant.components.tis_control.async_setup_entry",
        return_value=False,
    ):
        result = await flow.async_step_user({"port": "invalid!"})
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "invalid_port"}
