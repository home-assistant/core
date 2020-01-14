"""Define tests for the sun config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.sun import DOMAIN, config_flow

from tests.common import MockConfigEntry


async def test_more_than_one_instance_error(hass):
    """Test that errors are shown if someone attempts to add more than one sun entry."""
    MockConfigEntry(domain=DOMAIN, data={}).add_to_hass(hass)
    flow = config_flow.SunFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_step_user(hass):
    """Test that the user step works."""
    flow = config_flow.SunFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Default"
    assert result["data"] == {}
