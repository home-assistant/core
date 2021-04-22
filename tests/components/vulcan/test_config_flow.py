"""Test the Uonet+ Vulcan config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.vulcan import config_flow


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.VulcanFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
