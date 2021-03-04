"""Tests for spokestack_wakeword config flow."""
from unittest import mock

from homeassistant import setup
from homeassistant.components.spokestack_wakeword.config_flow import (
    SpokestackConfigFlow,
)
from homeassistant.components.spokestack_wakeword.const import DEFAULT_MODEL_URL, DOMAIN


@mock.patch("homeassistant.components.spokestack_wakeword.build_pipeline")
async def test_config_flow(_mock, hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "spokestack_wakeword", {})
    spokeflow = SpokestackConfigFlow()
    user_input = {"model_name": "my cool model", "model_url": DEFAULT_MODEL_URL}
    result = await spokeflow.async_step_user(user_input=user_input)
    assert result["type"] == "create_entry"
    assert result["title"] == DOMAIN.title()
    assert result["data"] == user_input
    await hass.async_block_till_done()


@mock.patch("homeassistant.components.spokestack_wakeword.build_pipeline")
async def test_config_flow_error(_mock, hass):
    """Test config flow with error."""
    await setup.async_setup_component(hass, "spokestack_wakeword", {})
    spokeflow = SpokestackConfigFlow()
    user_input = {"model_name": "my cool model", "model_url": "not a url"}
    result = await spokeflow.async_step_user(user_input=user_input)
    print(result)
    assert result["errors"] == {"base": "invalid_url"}
    await hass.async_block_till_done()
